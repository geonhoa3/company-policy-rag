"""음성 평가용 질문 세트.

세트를 넷으로 나눈 이유는 docs/stt-plan.md 6장에 있다.
요약하면, 모델을 고른 데이터로 성능을 보고하면 과적합이고,
2문항으로는 90% 같은 목표를 판정할 수 없기 때문이다.

  EVAL   40 : 보고용. 기존 텍스트 평가셋과 동일해야 1:1 비교가 된다
  NUMBER 15 : 조항 번호 인식률 전용. '제N조' 형태만
  PICK   10 : small/medium 선택 전용. 평가셋과 겹치지 않는다
  OBSERVE 3 : 점수에 넣지 않는 관찰용
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))

from eval_guard import HOLDOUT, QUESTIONS

# --- 1) 보고용 40문항: 텍스트 평가셋 그대로 ---------------------------------
EVAL = ([(f"eval{i:02d}", q) for i, (q, _, _) in enumerate(QUESTIONS, 1)] +
        [(f"hold{i:02d}", q) for i, (q, _, _) in enumerate(HOLDOUT, 1)])

# --- 2) 조항 번호 15문항: 제1~31조를 고르게, '제N조' 형태만 ------------------
# '제'를 뺀 변형은 OBSERVE 로 뺀다 (정규식을 넓히면 "3조 2교대"가 오탐되므로)
NUMBER = [
    ("num01", "제1조가 뭐야?"),
    ("num02", "제3조 내용 알려줘"),
    ("num03", "제5조는 어떤 내용이야?"),
    ("num04", "제7조가 뭐야?"),
    ("num05", "제9조 내용 알려줘"),
    ("num06", "제11조는 어떤 내용이야?"),
    ("num07", "제12조가 뭐야?"),
    ("num08", "제14조 내용 알려줘"),
    ("num09", "제16조는 어떤 내용이야?"),
    ("num10", "제19조가 뭐야?"),
    ("num11", "제22조 내용 알려줘"),
    ("num12", "제24조는 어떤 내용이야?"),
    ("num13", "제27조가 뭐야?"),
    ("num14", "제29조 내용 알려줘"),
    ("num15", "제31조는 어떤 내용이야?"),
]

# --- 3) 모델 선택용 10문항: 평가셋과 겹치지 않는 질문 -------------------------
PICK = [
    ("pick01", "지각하면 어떻게 되나요?"),
    ("pick02", "사직서는 언제까지 내야 해?"),
    ("pick03", "회사 기밀을 외부에 말하면 어떻게 돼?"),
    ("pick04", "유연근무 신청 조건이 뭐야?"),
    ("pick05", "상여금은 언제 나와?"),
    ("pick06", "표창은 어떤 경우에 받아?"),
    ("pick07", "업무 중 다치면 보상받을 수 있나요?"),
    ("pick08", "주말에 일하면 수당이 있어?"),
    ("pick09", "출장비는 어떻게 처리하나요?"),
    ("pick10", "근무 중에 흡연해도 되나요?"),
]

# --- 4) 관찰용: 점수에 넣지 않음 ---------------------------------------------
# obs03 은 정규식을 넓혔을 때 제3조로 오탐되는지 보는 탐침이다
OBSERVE = [
    ("obs01", "27조가 뭐야?"),
    ("obs02", "12조 내용 알려줘"),
    ("obs03", "3조 2교대 근무는 어떻게 돼?"),
]

SETS = {"eval": EVAL, "number": NUMBER, "pick": PICK, "observe": OBSERVE}
ALL = EVAL + NUMBER + PICK + OBSERVE


if __name__ == "__main__":
    for name, items in SETS.items():
        print(f"{name:<8} {len(items):>3}개")
    print(f"{'합계':<8} {len(ALL):>3}개")
    ids = [i for i, _ in ALL]
    assert len(ids) == len(set(ids)), "질문 ID 중복"
    print("ID 중복 없음")
