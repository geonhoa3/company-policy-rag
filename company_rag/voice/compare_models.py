"""small / medium 비교 — 모델 선택 전용 (실행: python voice/compare_models.py)

평가셋 40문항으로 모델을 고르면 '고른 데이터로 성능을 보고하는' 구조가 된다.
그래서 평가셋과 겹치지 않는 pick 10문항으로만 고른다 (docs/stt-plan.md 결정 8).

판단 기준: CER 목표(10% 이하)와 RTF 목표(0.3 이하)를 둘 다 만족하는 가장 작은 모델.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from metrics import cer, corpus_cer
from question_sets import PICK
from stt import STT

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
SIZES = sys.argv[1:] or ["small", "medium"]

summary = {}
for size in SIZES:
    stt = STT(size)
    stt.warmup(os.path.join(D, f"{PICK[0][0]}.wav"))     # 콜드 스타트를 측정에서 제외

    rows, rtfs = [], []
    for qid, want in PICK:
        r = stt.transcribe(os.path.join(D, f"{qid}.wav"))
        rows.append((qid, want, r.text_raw, cer(want, r.text_raw), r.rtf))
        rtfs.append(r.rtf)

    c = corpus_cer([(w, h) for _, w, h, _, _ in rows])
    rtf_mean = sum(rtfs) / len(rtfs)
    rtf_max = max(rtfs)
    summary[size] = (c, rtf_mean, rtf_max)

    print(f"\n{'='*74}\n[{size}]  CER {c:.1%}  /  RTF 평균 {rtf_mean:.3f} 최대 {rtf_max:.3f}\n")
    for qid, want, got, ce, rtf in rows:
        mark = "  " if ce == 0 else "⚠️"
        print(f" {mark} {qid}  CER {ce:>6.1%}  RTF {rtf:.3f}")
        if ce:
            print(f"      정답 {want}")
            print(f"      인식 {got}")

print(f"\n{'='*74}\n[종합]  CER 목표 ≤10%  /  RTF 목표 ≤0.3\n")
print(f"  {'모델':<10}{'CER':>9}{'RTF 평균':>11}{'RTF 최대':>11}   판정")
for size, (c, rm, rx) in summary.items():
    ok = c <= 0.10 and rx <= 0.30
    print(f"  {size:<10}{c:>8.1%}{rm:>11.3f}{rx:>11.3f}   {'✅ 목표 충족' if ok else '❌ 미달'}")

passed = [s for s, (c, _, rx) in summary.items() if c <= 0.10 and rx <= 0.30]
if passed:
    print(f"\n  → 목표를 만족하는 가장 작은 모델: {passed[0]}")
else:
    print("\n  → 목표를 만족하는 모델 없음. 목표 재검토 필요")
