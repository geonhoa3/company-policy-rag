"""검색 자가 검증 — build_index 실행 후 src/store.search()를 채점한다."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(os.path.dirname(__file__), "..")

def check():
    from src.store import load_index, search
    idx = os.path.join(BASE, "index")
    if not os.path.exists(os.path.join(idx, "vectors.npy")):
        print("❌ index/ 없음 — 먼저 'python build_index.py' 실행"); return

    chunks, vecs = load_index(idx)
    print(f"색인 로드: {len(chunks)}개 조항, 벡터 {vecs.shape}\n")

    # 질문 → 기대하는 조 번호
    cases = [
        ("수습 기간 임금은 몇 퍼센트야?", 5),
        ("연차 휴가 며칠 쓸 수 있어?", 12),
        ("결혼하면 휴가 며칠 나와?", 13),
        ("무단결근 며칠이면 징계 받아?", 27),
    ]
    ok = 0
    for q, expected in cases:
        results = search(q, chunks, vecs, k=3)
        top_chunk, score = results[0]
        top_no = top_chunk["article_no"]
        hit = "✅" if top_no == expected else "❌"
        if top_no == expected: ok += 1
        print(f"{hit} Q: {q}")
        print(f"    → 제{top_no}조 ({top_chunk['article_title']}) {score:.3f}  [기대 제{expected}조]")
    print(f"\n{ok}/{len(cases)} 통과")
    if ok == len(cases):
        print("✅ 검색 통과 — 질문 의미로 정확한 조항을 top에 올림")

if __name__ == "__main__":
    check()
