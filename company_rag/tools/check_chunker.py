"""청킹 자가 검증 — src/chunker.py의 chunk_by_article()를 채점한다."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
DOCX = os.path.join(os.path.dirname(__file__), "..", "data", "사규_취업규칙_샘플.docx")

def check():
    try:
        from src.loader import load_docx
        from src.chunker import chunk_by_article
    except Exception as e:
        print("❌ import 실패:", e); return

    paras = load_docx(DOCX)
    chunks = chunk_by_article(paras)

    # 1) list[dict]?
    assert isinstance(chunks, list), "반환이 list가 아님"
    assert all(isinstance(c, dict) for c in chunks), "원소가 dict가 아님"
    # 2) 필수 키?
    keys = {"chapter", "article_no", "article_title", "text"}
    assert all(keys <= set(c) for c in chunks), f"각 청크는 {keys} 키가 필요"
    # 3) 조 개수 = 31?
    nos = sorted(c["article_no"] for c in chunks)
    print(f"청크 수: {len(chunks)} (기대 31)")
    print(f"조 번호 범위: {min(nos)}~{max(nos)}")

    by_no = {c["article_no"]: c for c in chunks}

    # 4) 핵심 조가 온전히 묶였나 — 제12조(연차)는 항 4개가 다 들어와야
    c12 = by_no.get(12, {})
    ok12 = ("연차유급휴가" in c12.get("article_title","")
            and "15일" in c12.get("text","")
            and "25일" in c12.get("text",""))
    # 5) 조 헤딩이 text 안에 포함됐나 (출처 표기용)
    head_ok = "제12조" in c12.get("text","")
    # 6) 장 메타데이터가 맞게 붙었나
    c5 = by_no.get(5, {})
    chap_ok = "제2장" in c5.get("chapter","")

    print("제12조 연차 항 온전:", "✅" if ok12 else "❌", "| 헤딩 포함:", "✅" if head_ok else "❌")
    print("제5조 장 메타:", c5.get("chapter"), "->", "✅" if chap_ok else "❌")

    if len(chunks)==31 and ok12 and head_ok and chap_ok:
        print("✅ 청킹 통과 — 조 단위로 온전히 잘리고 메타데이터까지 부착됨")
    else:
        print("⚠️ 일부 기준 미달 — 위 ❌ 지점 확인")

    # 참고 출력: 첫 청크 미리보기
    if chunks:
        print("\n--- 첫 청크 미리보기 ---")
        print("chapter:", chunks[0]["chapter"])
        print("article:", chunks[0]["article_no"], chunks[0]["article_title"])
        print("text:", repr(chunks[0]["text"][:80]))

if __name__ == "__main__":
    check()
