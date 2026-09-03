"""로더 자가 검증 — src/loader.py의 load_docx()를 채점한다."""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DOCX = os.path.join(os.path.dirname(__file__), "..", "data", "사규_취업규칙_샘플.docx")

def check():
    try:
        from src.loader import load_docx
    except Exception as e:
        print("❌ src/loader.py 에서 load_docx 를 import 못함:", e); return

    paras = load_docx(DOCX)

    # 1) 리스트 반환?
    assert isinstance(paras, list), "반환값이 list가 아님"
    # 2) 원소가 문자열?
    assert all(isinstance(x, str) for x in paras), "원소 중 str이 아닌 게 있음"
    # 3) 빈 문단 제거됐나?
    assert all(x.strip() for x in paras), "빈/공백 문단이 남아있음"

    text = "\n".join(paras)
    # 4) 31개 조가 다 잡혔나?
    found = sorted(int(m) for m in re.findall(r"제(\d+)조", text))
    expected = list(range(1, 32))
    missing = set(expected) - set(found)

    print(f"문단 수: {len(paras)}")
    print(f"발견된 조: {len(set(found))}개 (기대 31개)")
    print("제목 포함:", "주식회사 한빛테크 취업규칙" in text)
    print("장 헤딩 예:", "제4장 휴일 및 휴가" in text)
    if missing:
        print("❌ 누락된 조:", sorted(missing))
    else:
        print("✅ 31조 전부 추출 성공 — 로더 통과")

if __name__ == "__main__":
    check()
