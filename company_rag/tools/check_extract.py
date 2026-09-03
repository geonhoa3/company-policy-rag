"""날짜 추출 자가 검증 — src/leave.py의 extract_hire_date() 채점. (모델 불필요)"""
import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def check():
    from src.leave import extract_hire_date, leave_days
    T = date(2026, 7, 8)
    tests = [
        ("작년 12월에 입사했으면 연차 며칠?", date(2025,12,1)),
        ("2025년 12월 3일에 입사", date(2025,12,3)),
        ("재작년 3월 입사", date(2024,3,1)),
        ("올해 1월에 들어왔어", date(2026,1,1)),
        ("연차 며칠 쓸 수 있어?", None),
        ("작년 13월", None),
    ]
    ok = 0
    for text, exp in tests:
        got = extract_hire_date(text, T)
        hit = got == exp
        ok += hit
        print(f"{'✅' if hit else '❌ 기대 '+str(exp)} | \"{text}\" → {got}")
    print(f"\n{ok}/{len(tests)} 통과", "— ✅ 추출 완성" if ok==len(tests) else "— ⚠️ TODO 확인")
    # end-to-end 한 방: 추출 → 계산
    d = extract_hire_date("작년 12월 입사", T)
    print("\n[연결 확인] '작년 12월 입사' →", d, "→ 연차", leave_days(d, T)["days"], "일")

if __name__ == "__main__":
    check()
