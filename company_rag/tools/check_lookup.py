"""조항 번호 조회 자가 검증 — src/store.py의 lookup_by_article_no() 채점.

번호 질문("제27조가 뭐야?")은 비교할 의미가 거의 없어 벡터 검색에 불리하다.
정규식으로 잡아 직접 꺼내는 경로가 제대로 붙었는지 확인한다.
임베딩이 필요한 검증은 뒤쪽에서만 하므로, 앞부분은 모델 없이도 돈다.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(os.path.dirname(__file__), "..")


def check():
    from src.store import load_index, lookup_by_article_no, search, EXACT_SCORE

    idx = os.path.join(BASE, "index")
    if not os.path.exists(os.path.join(idx, "vectors.npy")):
        print("❌ index/ 없음 — 먼저 'python build_index.py' 실행"); return
    chunks, vecs = load_index(idx)

    results = []

    # 1) 여러 표기 변형을 모두 잡는가
    print("[표기 변형]")
    for q, want in [("제3조가 뭐야?", 3), ("제 27 조 내용 알려줘", 27),
                    ("제12조는?", 12), ("제31조", 31)]:
        hit = lookup_by_article_no(q, chunks)
        ok = hit is not None and hit[0][0]["article_no"] == want
        print(f"  {'✅' if ok else '❌'} {q!r:<22} → 제{hit[0][0]['article_no']}조" if hit
              else f"  ❌ {q!r:<22} → 못 찾음")
        results.append(ok)

    # 2) 번호가 없는 질문은 건드리지 않는다 (벡터 검색으로 넘어가야 함)
    print("\n[비대상 통과]")
    for q in ["연차 며칠 쓸 수 있어?", "무단결근하면 징계받아?"]:
        ok = lookup_by_article_no(q, chunks) is None
        print(f"  {'✅' if ok else '❌'} {q!r} → 벡터 검색으로 위임")
        results.append(ok)

    # 3) 존재하지 않는 조 번호도 벡터 검색으로 위임
    ok = lookup_by_article_no("제99조가 뭐야?", chunks) is None
    print(f"  {'✅' if ok else '❌'} '제99조가 뭐야?' (없는 조) → 벡터 검색으로 위임")
    results.append(ok)

    # 4) search() 통합 — 번호 질문은 정확 일치 점수로 반환되어 신뢰도 경고를 넘긴다
    print("\n[search 통합]")
    for q, want in [("제3조가 뭐야?", 3), ("제27조가 뭐야?", 27)]:
        hits = search(q, chunks, vecs, k=3)
        top_c, top_s = hits[0]
        ok = top_c["article_no"] == want and top_s == EXACT_SCORE
        print(f"  {'✅' if ok else '❌'} {q!r} → 제{top_c['article_no']}조 "
              f"({top_c['article_title']}), 점수 {top_s} ≥ 0.5 → 경고 안 뜸")
        results.append(ok)

    # 5) 의미 질문은 기존 벡터 경로 그대로 (회귀)
    hits = search("연차 며칠 쓸 수 있어?", chunks, vecs, k=3)
    ok = hits[0][0]["article_no"] == 12 and hits[0][1] < EXACT_SCORE
    print(f"  {'✅' if ok else '❌'} '연차 며칠 쓸 수 있어?' → 제{hits[0][0]['article_no']}조, "
          f"유사도 {hits[0][1]:.3f} (벡터 경로 유지)")
    results.append(ok)

    print(f"\n{sum(results)}/{len(results)} 통과 —",
          "✅ 번호 조회 라우팅 완성" if all(results) else "⚠️ 위 ❌ 지점 확인")


if __name__ == "__main__":
    check()
