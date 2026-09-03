# src/answer.py
import os, ollama
from datetime import date
from src.store import load_index, search

BASE = os.path.dirname(os.path.abspath(__file__))
INDEX_DIR = os.path.join(BASE, "..", "index")
MODEL = "qwen2.5:7b"          # 여기만 바꾸면 모델 교체
# 규정 QA는 같은 질문에 늘 같은 답이 나와야 한다 → 샘플링 끔
OPTIONS = {"temperature": 0}

SYSTEM = (
    "너는 회사 규정 안내 도우미다. "
    "아래 '규정' 안의 내용만 근거로 답하라. "
    "규정에 명시되지 않은 숫자·기간·한도(예: 누적 상한)를 절대 지어내거나 덧붙이지 마라. "
    "규정에 없는 내용은 '규정에 없습니다'라고 답하라. "
    # 여기서 '단계별로 계산하라'고 시키면 아래 [코드 계산 결과] 주입과 정면으로 충돌한다.
    # 실측 결과 그 버전은 코드 계산값을 5회 중 2회만 따랐다.
    "[코드 계산 결과]가 주어지면 그 숫자를 그대로 최종 답으로 사용하고, "
    "스스로 날짜·기간을 다시 계산하지 마라. "
    "답이 규정에 있으면 끝에 근거 조항을 (제N조) 형태로 표기하라."
)

def _system_with_date() -> str:
    """오늘 날짜를 주입한 시스템 프롬프트 (기간 계산 기준점)."""
    return SYSTEM + f"\n참고: 오늘 날짜는 {date.today().isoformat()}이다. 기간 계산은 이 날짜를 기준으로 하라."

_cache = None
def _load():
    global _cache
    if _cache is None:
        _cache = load_index(INDEX_DIR)
    return _cache

def answer(query: str, k: int = 3):
    chunks, vecs = _load()
    hits = search(query, chunks, vecs, k=k)     # 슬롯4 재사용
    # TODO) hits 로 '규정' 컨텍스트 문자열 만들기
    #  힌트: "\n\n".join(c["text"] for c, score in hits)
    context = "\n\n".join(c["text"] for c, score in hits)
    user_prompt = f"규정:\n{context}\n\n질문: {query}"
    resp = ollama.chat(model=MODEL, options=OPTIONS, messages=[
        {"role": "system", "content": _system_with_date()},
        {"role": "user", "content": user_prompt},
    ])
    return resp["message"]["content"], hits


def condense_query(question: str, history: list[dict]) -> str:
    """이전 대화를 참고해 후속질문을 독립형 질문으로 재작성 (검색용)."""
    if not history:
        return question                      # 첫 질문이면 재작성 불필요
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history)
    prompt = (
        "다음 대화 맥락을 참고해, 마지막 질문을 그것만 보고도 이해되는 "
        "독립적인 질문으로 다시 써라. 설명 없이 질문 문장만 출력.\n\n"
        f"[대화]\n{convo}\n\n[마지막 질문] {question}"
    )
    resp = ollama.chat(model=MODEL, options=OPTIONS,
                       messages=[{"role": "user", "content": prompt}])
    return resp["message"]["content"].strip()


def answer_with_history(question: str, history: list[dict], k: int = 3, extra_context: str = ""):
    chunks, vecs = _load()
    search_query = condense_query(question, history)   # 검색용 독립 질문
    hits = search(search_query, chunks, vecs, k=k)
    context = "\n\n".join(c["text"] for c, _ in hits)

    # 코드가 미리 계산한 사실(예: 연차 일수)을 근거로 주입. LLM은 이 숫자를 그대로 쓴다.
    facts = f"\n[코드 계산 결과 — 이 숫자를 정답으로 사용하고 다시 계산하지 마라]\n{extra_context}\n" if extra_context else ""

    messages = [{"role": "system", "content": _system_with_date()}]
    messages += history                                # 지난 대화 그대로 전달
    messages.append({"role": "user", "content": f"규정:\n{context}\n{facts}\n질문: {question}"})

    resp = ollama.chat(model=MODEL, options=OPTIONS, messages=messages)
    return resp["message"]["content"], hits, search_query