# src/leave.py
from datetime import date
import re

_REL = {"올해": 0, "금년": 0, "작년": 1, "재작년": 2}

def _safe(y, mo, d):
    try: return date(y, mo, d)
    except ValueError: return None       # 13월 같은 잘못된 날짜 → None (안전 실패)

def extract_hire_date(text: str, today: date | None = None):
    """채팅 문장에서 입사일 추출. 못 찾으면 None."""
    if today is None:
        today = date.today()
    # 절대: 2025년 12월 (3일)
    m = re.search(r"(20\d{2})\s*년\s*(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?", text)
    if m:
        return _safe(int(m.group(1)), int(m.group(2)), int(m.group(3) or 1))
    # 상대: 작년/재작년/올해 N월 (N일)
    m = re.search(r"(올해|금년|작년|재작년)\s*(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?", text)
    if m:
        # TODO) 상대 표현을 실제 연도로: 오늘 연도에서 _REL 만큼 빼기
        #  힌트: y = today.year - _REL[m.group(1)]
        y = today.year - _REL[m.group(1)]
        return _safe(y, int(m.group(2)), int(m.group(3) or 1))
    return None

def months_between(start: date, end: date) -> int:
    """만으로 경과한 개월 수 (일자 안 지났으면 -1)."""
    m = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        m -= 1
    return max(m, 0)

def leave_days(hire_date: date, as_of: date | None = None) -> dict:
    if as_of is None:
        as_of = date.today()
    months = months_between(hire_date, as_of)
    years = months // 12

    # TODO) 제12조 규칙 적용
    if years < 1:
        # 1년 미만: 개근 개월당 1일 (항2)
        days = months                          # 힌트: months
        basis = f"근속 {months}개월(1년 미만) → 1개월당 1일"
    else:
        # 3년 이상 매 2년 +1일, 25일 한도 (항1·3)
        extra = (years - 1) // 2
        days = min(15 + extra, 25)                          # 힌트: min(15 + extra, 25)
        basis = f"근속 {years}년 → 기본 15일 + 가산 {extra}일 (25일 한도)"

    return {"months": months, "years": years, "days": days, "basis": basis}