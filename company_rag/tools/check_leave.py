"""연차 계산 자가 검증 — src/leave.py의 leave_days() 채점. (모델 불필요)"""
import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def check():
    from src.leave import leave_days
    cases = [
        ("작년 12월 입사, 오늘 7/8", date(2025,12,1), date(2026,7,8), 7),
        ("만 1년 반",              date(2025,1,1),  date(2026,7,8), 15),
        ("6년차",                 date(2020,1,1),  date(2026,7,8), 17),
        ("26년차(상한 25)",        date(2000,1,1),  date(2026,7,8), 25),
        ("입사 당일",              date(2026,7,8),  date(2026,7,8), 0),
    ]
    ok = 0
    for name, h, a, exp in cases:
        r = leave_days(h, a)
        hit = r["days"] == exp
        ok += hit
        print(f"{'✅' if hit else '❌ 기대'+str(exp)} {name}: {r['days']}일  [{r['basis']}]")
    print(f"\n{ok}/{len(cases)} 통과", "— ✅ 계산 함수 완성" if ok==len(cases) else "— ⚠️ TODO 확인")

if __name__ == "__main__":
    check()
