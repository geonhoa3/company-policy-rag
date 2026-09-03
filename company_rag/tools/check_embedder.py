"""임베딩 자가 검증 — src/embedder.py의 embed_texts()를 채점한다.
   ※ 첫 실행 시 임베딩 모델을 다운로드하므로 시간이 걸린다."""
import sys, os, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
DOCX = os.path.join(os.path.dirname(__file__), "..", "data", "사규_취업규칙_샘플.docx")

def check():
    from src.loader import load_docx
    from src.chunker import chunk_by_article
    from src.embedder import embed_texts

    chunks = chunk_by_article(load_docx(DOCX))
    texts = [c["text"] for c in chunks]

    print("임베딩 중... (첫 실행이면 모델 다운로드로 오래 걸림)")
    vecs = embed_texts(texts)

    # 1) 모양: (조 개수, 차원)
    assert vecs.ndim == 2, "2차원 배열이어야 함"
    assert vecs.shape[0] == len(texts), f"행 수가 청크 수({len(texts)})와 달라"
    print(f"벡터 배열 모양: {vecs.shape}  (조 {vecs.shape[0]}개 × {vecs.shape[1]}차원)")

    # 2) 정규화됐나 (각 벡터 길이 ≈ 1)
    norms = np.linalg.norm(vecs, axis=1)
    normalized = np.allclose(norms, 1.0, atol=1e-2)
    print("정규화 여부:", "✅" if normalized else "❌ (normalize_embeddings=True 확인)")

    # 3) 의미 검색이 실제로 되나 — 이게 임베딩의 존재 이유
    q = embed_texts(["연차 휴가는 며칠까지 쓸 수 있나요?"])[0]
    sims = vecs @ q                      # 정규화돼서 내적 = 코사인 유사도
    top = int(np.argmax(sims))
    top_no = chunks[top]["article_no"]
    print(f"\n질문: '연차 휴가는 며칠까지?'")
    print(f"가장 가까운 조: 제{top_no}조 ({chunks[top]['article_title']}) 유사도 {sims[top]:.3f}")
    if top_no == 12:
        print("✅ 임베딩 통과 — '휴가'라는 단어 없이도 연차 조항(제12조)을 찾아냄")
    else:
        print("⚠️ 제12조를 못 찾음 — 모델/정규화 확인")

if __name__ == "__main__":
    check()
