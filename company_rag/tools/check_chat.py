"""대화 이력 자가 검증 — condense_query / answer_with_history 채점.
   ※ Ollama 실행 중이어야 함."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def check():
    from src.answer import condense_query, answer_with_history, _load
    from src.store import search

    # 1턴: 연차 질문 (히스토리 없음)
    try:
        text1, hits1, sq1 = answer_with_history("연차 휴가 며칠 쓸 수 있어?", [])
    except Exception as e:
        print("❌ Ollama 연결 실패? 서버 확인. 에러:", repr(e)); return
    print("Q1: 연차 며칠?")
    print("  검색질문:", sq1)
    print("  답변:", text1.strip()[:120], "...")

    history = [
        {"role": "user", "content": "연차 휴가 며칠 쓸 수 있어?"},
        {"role": "assistant", "content": text1},
    ]

    # 2턴: 대명사 후속질문 — 재작성이 핵심
    follow = "그럼 3년 넘게 일하면 며칠 늘어나?"
    sq2 = condense_query(follow, history)
    print(f"\nQ2(후속): {follow}")
    print("  → 재작성:", sq2)

    # 재작성된 질문으로 검색했을 때 제12조가 top인지
    chunks, vecs = _load()
    top = search(sq2, chunks, vecs, k=1)[0][0]
    print(f"  → 검색 top: 제{top['article_no']}조 ({top['article_title']})")

    text2, hits2, _ = answer_with_history(follow, history)
    print("  답변:", text2.strip()[:160])

    rewrite_ok = ("연차" in sq2 or "휴가" in sq2)   # 대명사가 실제 주제로 바뀜
    retrieve_ok = (top["article_no"] == 12)
    print("\n재작성에 주제 복원:", "✅" if rewrite_ok else "❌",
          "| 후속질문이 제12조 검색:", "✅" if retrieve_ok else "❌")
    if rewrite_ok and retrieve_ok:
        print("✅ 대화 이력 통과 — 후속질문의 맥락을 복원해 정확히 검색함")

if __name__ == "__main__":
    check()
