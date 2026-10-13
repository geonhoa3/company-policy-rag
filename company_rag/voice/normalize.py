"""STT 출력 전용 텍스트 정규화.

조항 번호 정규식(제\\s*(\\d+)\\s*조)이 매칭에 실패하면 번호 질문이 벡터 검색으로
떨어지는데, 번호 질문의 벡터 점수는 0.43~0.50 이라 그대로 거부된다.
그래서 STT 가 흔히 깨뜨리는 두 가지를 되돌린다.

  1) 한글 숫자   "제이십칠조" → "제27조"
  2) 단위 글자   "제11주는"   → "제11조는"

왜 'STT 출력에만' 적용하는가:
  텍스트 입력 경로를 건드리지 않아야 기존 평가(30문항 + 홀드아웃 10문항)
  결과가 그대로 유지된다. docs/stt-plan.md 3-3 참고.

왜 조사(가/는/를...)가 올 때만 바꾸는가:
  "제3주차 교육", "제2주 교육 일정" 처럼 '주'가 진짜 '주(week)'인 표현이 있다.
  조사가 바로 붙는 경우로 좁히면 이들을 건드리지 않는다.
  정규식을 '제?'로 넓히지 않기로 한 것과 같은 판단이다 — 기능을 넓히기 전에
  그 변경이 오탐을 만드는지 먼저 본다.
"""
import re

_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
          "육": 6, "륙": 6, "칠": 7, "팔": 8, "구": 9}

# '제' 와 '조' 사이가 한글 숫자로만 채워진 경우
_ARTICLE_KO = re.compile(r"제\s*([일이삼사오육륙칠팔구십]+)\s*조")

# '조' 를 '주'/'초' 로 잘못 받아쓴 경우. 바로 뒤에 조사가 올 때만 바꾼다.
_JOSA = "가는은를이에의도와과로만"
_UNIT_SLIP = re.compile(rf"제\s*(\d+)\s*[주초](?=[{_JOSA}])")


def sino_to_int(s: str):
    """한자어 수 읽기를 정수로. 1~99 만 다룬다 (조항 번호 범위)."""
    s = s.strip()
    if not s or any(c not in _DIGIT and c != "십" for c in s):
        return None
    if "십" not in s:
        return _DIGIT.get(s) if len(s) == 1 else None

    tens_part, _, ones_part = s.partition("십")
    if len(tens_part) > 1 or len(ones_part) > 1:
        return None
    if tens_part and tens_part not in _DIGIT:
        return None
    if ones_part and ones_part not in _DIGIT:
        return None
    tens = _DIGIT.get(tens_part, 1) if tens_part else 1      # '십이' 는 앞자리 생략
    ones = _DIGIT.get(ones_part, 0) if ones_part else 0
    return tens * 10 + ones


def normalize_article_numbers(text: str) -> str:
    """'제이십칠조' → '제27조'. 숫자로 이미 적힌 것은 그대로 둔다."""
    def sub(m):
        n = sino_to_int(m.group(1))
        return f"제{n}조" if n is not None else m.group(0)
    return _ARTICLE_KO.sub(sub, text)


def normalize_unit_slip(text: str) -> str:
    """'제11주는' → '제11조는'. 조사가 바로 붙을 때만 바꾼다."""
    return _UNIT_SLIP.sub(lambda m: f"제{m.group(1)}조", text)


def normalize_stt(text: str) -> str:
    """STT 출력에 적용할 정규화 전체."""
    return normalize_unit_slip(normalize_article_numbers(text))


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    cases = [
        # --- 한글 숫자 (v2 가설) ---
        ("제이십칠조가 뭐야?", "제27조가 뭐야?"),
        ("제 이십칠 조가 뭐야?", "제27조가 뭐야?"),
        ("제십이조 내용 알려줘", "제12조 내용 알려줘"),
        ("제이십조 내용 알려줘", "제20조 내용 알려줘"),
        ("제삼십일조는 어떤 내용이야?", "제31조는 어떤 내용이야?"),
        # --- 단위 글자 (실측에서 실제로 나온 오류) ---
        ("제11주는 어떤 내용이야?", "제11조는 어떤 내용이야?"),
        ("제22주는 어떤 내용이야?", "제22조는 어떤 내용이야?"),
        ("제31주는 어떤 내용이야?", "제31조는 어떤 내용이야?"),
        ("제27초가 뭐야?", "제27조가 뭐야?"),
        ("제 11 주를 알려줘", "제11조를 알려줘"),
        # --- 오탐 탐침: 바꾸면 안 되는 것 ---
        ("제3주차 교육은 언제야?", "제3주차 교육은 언제야?"),
        ("제2주 교육 일정 알려줘", "제2주 교육 일정 알려줘"),
        ("20초 동안 기다려", "20초 동안 기다려"),
        ("3주 동안 휴가 쓸 수 있어?", "3주 동안 휴가 쓸 수 있어?"),
        ("제2주간 근무표", "제2주간 근무표"),
        ("제1주년 행사", "제1주년 행사"),
        # --- 기존 동작 유지 ---
        ("제27조가 뭐야?", "제27조가 뭐야?"),
        ("이십칠조가 뭐야?", "이십칠조가 뭐야?"),
        ("삼일절에도 근무하나요?", "삼일절에도 근무하나요?"),
        ("3조 2교대 근무는 어떻게 돼?", "3조 2교대 근무는 어떻게 돼?"),
        # --- 조사가 없으면 바꾸지 않는다 (제2주 교육 과 구분 불가) ---
        ("제 20초 내용 알려줘", "제 20초 내용 알려줘"),
    ]
    ok = 0
    for src, want in cases:
        got = normalize_stt(src)
        good = got == want
        ok += good
        print(f"  {'✅' if good else '❌'} {src!r} → {got!r}" + ("" if good else f"  (기대 {want!r})"))
    print(f"\n{ok}/{len(cases)} 통과")
