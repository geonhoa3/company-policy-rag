"""STT initial_prompt 용 규정 어휘.

용어를 **규정 문서의 조항 제목**에서 뽑는다. 평가 질문에서 뽑으면
정답을 미리 알려주는 셈이라 평가가 무의미해진다 (docs/stt-plan.md).

조항 제목은 색인에 이미 메타데이터로 들어가 있어 따로 관리할 필요가 없다.
문서가 바뀌면 용어도 자동으로 따라온다.
"""
import json
import os

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def regulation_terms():
    """조항 제목과 장 제목을 중복 없이 순서대로."""
    chunks = json.load(open(os.path.join(BASE, "index", "chunks.json"), encoding="utf-8"))
    out, seen = [], set()
    for c in sorted(chunks, key=lambda x: x["article_no"]):
        for t in (c["chapter"], c["article_title"]):
            t = t.strip()
            # "제4장 휴일 및 휴가" 에서 장 번호를 떼고 제목만 남긴다
            if t.startswith("제") and "장" in t[:5]:
                t = t.split("장", 1)[1].strip()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
    return out


def initial_prompt():
    """Whisper 디코딩을 규정 어휘 쪽으로 기울이는 문장.

    조항 번호를 '제N조' 로 받아쓰도록 형식 예시도 함께 준다
    (실측에서 '조' 가 '초'/'주' 로 자주 바뀌었다).
    """
    terms = ", ".join(regulation_terms())
    return f"회사 취업규칙 질의응답. 제1조, 제12조, 제27조 같은 조항 번호. {terms}."


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    terms = regulation_terms()
    print(f"조항·장 제목에서 뽑은 용어 {len(terms)}개\n")
    print("  " + ", ".join(terms))
    p = initial_prompt()
    print(f"\ninitial_prompt ({len(p)}자)\n")
    print(f"  {p}")
