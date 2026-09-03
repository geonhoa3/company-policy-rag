"""LLM 답변 자가 검증 — src/answer.py의 answer()를 채점한다.
   ※ Ollama 실행 중이고 모델(qwen2.5:7b)이 pull 돼 있어야 함."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def check():
    from src.answer import answer

    # 1) 규정 안 질문 — 사실 정확 + 출처 표기
    try:
        text, hits = answer("입사 1년차 연차 휴가 며칠 쓸 수 있어?")
    except Exception as e:
        print("❌ Ollama 연결 실패 가능 — 아래 확인:")
        print("   1) Ollama 설치 후 실행 중인지  2) 'ollama pull qwen2.5:7b' 했는지")
        print("   에러:", repr(e)); return

    print("Q1: 연차 며칠?")
    print("답변:", text.strip())
    fact_ok = "15" in text
    cite_ok = any(c["article_no"] == 12 for c, _ in hits)
    print("  → 15(일) 언급:", "✅" if fact_ok else "❌",
          "| 검색 근거 제12조:", "✅" if cite_ok else "❌")

    # 2) 규정 밖 질문 — 환각 방지 (핵심 안전 테스트)
    text2, _ = answer("회사에 헬스장이 있나요?")
    print("\nQ2: 헬스장 있어? (규정에 없는 내용)")
    print("답변:", text2.strip())
    no_ok = "없" in text2
    print("  → '없음' 류 응답:", "✅" if no_ok else "❌ 환각 위험(지어냄)")

    print("\n" + ("✅ 답변 슬롯 통과 — 근거로 답하고, 없는 건 없다고 함"
                  if (fact_ok and no_ok) else "⚠️ 위 ❌ 지점 확인"))

if __name__ == "__main__":
    check()
