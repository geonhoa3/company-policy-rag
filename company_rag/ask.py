# ask.py
from src.answer import answer_with_history

def main():
    print("=== 회사 규정 QA (종료: quit) ===\n")
    history = []                              # 대화 기억 저장소
    while True:
        q = input("질문> ").strip()
        if q.lower() in ("quit", "exit", "q", ""):
            print("종료."); break
        text, hits, sq = answer_with_history(q, history)
        if sq != q:
            print(f"  (검색용 재작성: {sq})")   # 재작성이 어떻게 됐는지 눈으로 확인
        print("\n" + text.strip())
        cites = ", ".join(f"제{c['article_no']}조({c['article_title']})" for c, _ in hits)
        print(f"[근거: {cites}]\n")
        # 이번 턴을 히스토리에 저장 (원 질문 그대로 — 자연스러운 대화 유지)
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": text})

if __name__ == "__main__":
    main()