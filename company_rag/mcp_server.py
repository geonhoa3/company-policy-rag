"""mcp_server.py — 규정봇을 MCP 도구로 노출한다 (실행: python mcp_server.py)

Streamlit UI(app.py), CLI(ask.py)에 이어 **세 번째 표면**이다. 셋 다 src/ 의
같은 코어를 쓰고, 이 파일은 그 코어를 MCP 도구·리소스로 감싸기만 한다.

설계 판단 — 서버는 LLM 을 호출하지 않는다:
  MCP 호스트(Claude Desktop 등)가 이미 LLM 이다. 여기서 Ollama 를 또 부르면
  LLM 이 이중으로 겹쳐 느려지고, 작은 모델이 큰 모델의 답을 깎아낸다.
  그래서 검색·조회·계산만 도구로 주고 생성은 호스트에 맡긴다.

  대신 신뢰도 가드는 응답에 실어 보낸다. has_evidence=false 와 instruction 을
  읽은 호스트가 답변을 멈추도록 하는 것이 app.py 의 생성 차단과 같은 역할이다.
"""
import os
import sys
from datetime import date

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.answer import CONF_THRESHOLD, NO_EVIDENCE
from src.leave import extract_hire_date, leave_days
from src.store import EXACT_SCORE, load_index, search

BASE = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(BASE, "index")

mcp = FastMCP("company-policy-rag")

_cache = None


def _load():
    """색인은 무겁다(bge-m3 로드 포함) → 첫 호출 때 한 번만."""
    global _cache
    if _cache is None:
        _cache = load_index(INDEX_DIR)
    return _cache


def _fmt(chunk: dict, score: float) -> dict:
    out = {
        "article_no": chunk["article_no"],
        "article_title": chunk["article_title"],
        "chapter": chunk["chapter"],
        "text": chunk["text"],
    }
    if score == EXACT_SCORE:
        out["match"] = "exact"          # 번호로 직접 찾음 — 유사도가 아니다
    else:
        out["similarity"] = round(float(score), 3)
    if chunk.get("n_parts", 1) > 1:
        out["part"] = f"{chunk['part']}/{chunk['n_parts']}"
    return out


@mcp.tool()
def search_regulations(query: str, k: int = 3) -> dict:
    """취업규칙에서 질문과 관련된 조항을 찾는다.

    질문에 "제N조"가 있으면 벡터 검색 대신 해당 조항을 직접 조회한다
    (번호 질문은 비교할 의미가 적어 유사도가 낮게 나오기 때문).

    has_evidence 가 false 면 근거를 찾지 못한 것이다. 이때는 반환된 조항을
    근거로 답을 지어내지 말고, 규정에 없다고 사용자에게 알려야 한다.

    Args:
        query: 사용자 질문 (예: "연차 며칠 쓸 수 있어?", "제27조가 뭐야?")
        k: 가져올 조항 수 (기본 3). 번호 조회일 때는 무시된다.
    """
    chunks, vecs = _load()
    hits = search(query, chunks, vecs, k=k)
    top = hits[0][1] if hits else 0.0
    exact = top == EXACT_SCORE
    has_evidence = exact or top >= CONF_THRESHOLD

    result = {
        "query": query,
        "matched_by": "article_number" if exact else "vector_search",
        "has_evidence": has_evidence,
        "articles": [_fmt(c, s) for c, s in hits],
    }
    if not exact:
        result["top_similarity"] = round(float(top), 3)
        result["threshold"] = CONF_THRESHOLD
    if not has_evidence:
        result["instruction"] = (
            f"{NO_EVIDENCE} 최고 유사도 {top:.3f} 가 임계값 {CONF_THRESHOLD} 에 못 미친다. "
            "위 조항들을 근거로 답을 만들지 말고, 규정에서 근거를 찾지 못했다고 답하라."
        )
    return result


@mcp.tool()
def get_article(article_no: int) -> dict:
    """조항 번호로 취업규칙 조문을 그대로 가져온다.

    검색이 아니라 조회이므로 유사도와 무관하게 정확하다.
    긴 조항이 항 단위로 쪼개져 있으면 조각을 전부 순서대로 반환한다.

    Args:
        article_no: 조 번호 (예: 12 → 제12조)
    """
    chunks, _ = _load()
    hits = [c for c in chunks if c["article_no"] == article_no]
    if not hits:
        available = sorted({c["article_no"] for c in chunks})
        return {"found": False,
                "error": f"제{article_no}조가 없습니다.",
                "available_articles": f"제{available[0]}조 ~ 제{available[-1]}조"}
    hits.sort(key=lambda c: c.get("part", 1))
    return {"found": True,
            "article_no": article_no,
            "parts": [_fmt(c, EXACT_SCORE) for c in hits]}


@mcp.tool()
def calculate_leave(hire_date: str, as_of: str = "") -> dict:
    """입사일로 연차 휴가 일수를 계산한다 (제12조 규칙).

    날짜 계산은 LLM 이 자주 틀리는 지점이라 코드로 처리한다.
    이 도구가 돌려준 days 를 그대로 사용하고, 직접 다시 계산하지 마라.

    Args:
        hire_date: 입사일. "2025-12-01" 또는 "작년 12월" 같은 표현도 된다.
        as_of: 기준일 (YYYY-MM-DD). 비우면 오늘.
    """
    hire = extract_hire_date(hire_date)
    if hire is None:
        try:
            hire = date.fromisoformat(hire_date.strip())
        except ValueError:
            return {"ok": False,
                    "error": f"입사일을 해석하지 못했습니다: {hire_date!r}",
                    "hint": "'2025-12-01' 또는 '작년 12월' 형식으로 주세요."}

    base = None
    if as_of:
        try:
            base = date.fromisoformat(as_of.strip())
        except ValueError:
            return {"ok": False, "error": f"기준일 형식 오류: {as_of!r} (YYYY-MM-DD)"}

    r = leave_days(hire, base)
    return {"ok": True,
            "hire_date": hire.isoformat(),
            "as_of": (base or date.today()).isoformat(),
            "months": r["months"],
            "years": r["years"],
            "days": r["days"],
            "basis": r["basis"],
            "source": "제12조 (연차유급휴가)"}


@mcp.resource("regulation://articles")
def list_articles() -> str:
    """취업규칙 전체 조항 목록 (장 · 조 번호 · 제목)."""
    chunks, _ = _load()
    seen, lines = set(), []
    for c in sorted(chunks, key=lambda x: (x["article_no"], x.get("part", 1))):
        if c["article_no"] in seen:
            continue
        seen.add(c["article_no"])
        lines.append(f"{c['chapter']} | 제{c['article_no']}조 ({c['article_title']})")
    return "\n".join(lines)


@mcp.resource("regulation://article/{article_no}")
def read_article(article_no: str) -> str:
    """조항 번호로 조문 원문을 읽는다."""
    chunks, _ = _load()
    hits = [c for c in chunks if str(c["article_no"]) == str(article_no)]
    if not hits:
        return f"제{article_no}조가 없습니다."
    hits.sort(key=lambda c: c.get("part", 1))
    return "\n\n".join(c["text"] for c in hits)


if __name__ == "__main__":
    mcp.run()
