"""STT 출력 전용 한글 숫자 정규화.

Whisper 가 "제27조" 를 "제이십칠조" 처럼 한글 숫자로 받아쓰면
조항 번호 정규식(제\\s*(\\d+)\\s*조)이 매칭에 실패해 벡터 검색으로 떨어진다.
번호 질문의 벡터 점수는 0.43~0.50 이라 그대로 거부된다.

왜 '제...조' 안에서만 바꾸는가:
  문장 전체의 한글 숫자를 바꾸면 "삼일절", "이사회" 같은 말까지 건드린다.
  조항 번호 조회를 살리는 것이 목적이므로 그 문맥으로 범위를 좁힌다.

왜 STT 출력에만 적용하는가:
  텍스트 입력 경로를 건드리지 않아야 기존 평가(30문항 + 홀드아웃 10문항)
  결과가 그대로 유지된다. docs/stt-plan.md 3-3 참고.
"""
import re

_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5,
          "육": 6, "륙": 6, "칠": 7, "팔": 8, "구": 9}

# '제' 와 '조' 사이가 한글 숫자로만 채워진 경우
_ARTICLE_KO = re.compile(r"제\s*([일이삼사오육륙칠팔구십]+)\s*조")


def sino_to_int(s: str):
    """한자어 수 읽기를 정수로. 1~99 만 다룬다 (조항 번호 범위).

    '칠'→7, '십'→10, '십이'→12, '이십'→20, '이십칠'→27
    해석할 수 없으면 None.
    """
    s = s.strip()
    if not s or any(c not in _DIGIT and c != "십" for c in s):
        return None

    if "십" not in s:
        return _DIGIT.get(s) if len(s) == 1 else None

    tens_part, _, ones_part = s.partition("십")
    if len(tens_part) > 1 or len(ones_part) > 1:
        return None

    tens = _DIGIT.get(tens_part, 1) if tens_part else 1      # '십이' 는 앞자리 생략
    ones = _DIGIT.get(ones_part, 0) if ones_part else 0
    if tens_part and tens_part not in _DIGIT:
        return None
    if ones_part and ones_part not in _DIGIT:
        return None
    return tens * 10 + ones


def normalize_article_numbers(text: str) -> str:
    """'제이십칠조' → '제27조'. 숫자로 이미 적힌 것은 그대로 둔다."""
    def sub(m):
        n = sino_to_int(m.group(1))
        return f"제{n}조" if n is not None else m.group(0)
    return _ARTICLE_KO.sub(sub, text)


if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    cases = [
        # (입력, 기대)
        ("제이십칠조가 뭐야?", "제27조가 뭐야?"),
        ("제 이십칠 조가 뭐야?", "제27조가 뭐야?"),
        ("제십이조 내용 알려줘", "제12조 내용 알려줘"),
        ("제이조는 어떤 내용이야?", "제2조는 어떤 내용이야?"),
        ("제이십조 내용 알려줘", "제20조 내용 알려줘"),
        ("제삼십일조는 어떤 내용이야?", "제31조는 어떤 내용이야?"),
        ("제일조가 뭐야?", "제1조가 뭐야?"),
        # 이미 숫자면 그대로
        ("제27조가 뭐야?", "제27조가 뭐야?"),
        # '제'가 없으면 건드리지 않는다 (정규식을 넓히지 않기로 한 결정과 일관)
        ("이십칠조가 뭐야?", "이십칠조가 뭐야?"),
        # 조항 번호 문맥이 아니면 그대로
        ("삼일절에도 근무하나요?", "삼일절에도 근무하나요?"),
        ("이사회 의결이 필요한가요?", "이사회 의결이 필요한가요?"),
        ("3조 2교대 근무는 어떻게 돼?", "3조 2교대 근무는 어떻게 돼?"),
    ]
    ok = 0
    for src, want in cases:
        got = normalize_article_numbers(src)
        good = got == want
        ok += good
        print(f"  {'✅' if good else '❌'} {src!r} → {got!r}" + ("" if good else f"  (기대 {want!r})"))
    print(f"\n{ok}/{len(cases)} 통과")

    print("\n[sino_to_int]")
    for s, want in [("일", 1), ("칠", 7), ("십", 10), ("십이", 12), ("이십", 20),
                    ("이십칠", 27), ("삼십일", 31), ("백", None), ("", None)]:
        got = sino_to_int(s)
        print(f"  {'✅' if got == want else '❌'} {s!r:<8} → {got}")
