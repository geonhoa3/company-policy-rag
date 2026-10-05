"""신뢰도 가드 자가 검증 — 근거가 약하면 LLM 호출 '자체'를 건너뛰는지 채점.

경고만 띄우는 것과 생성을 막는 것은 화면만 봐서는 구분되지 않는다.
차이는 ollama.chat 호출 횟수로만 증명되므로, 스텁으로 갈아끼워 직접 센다.
※ 검색(임베딩)은 실제로 돌지만 LLM 은 호출되지 않으므로 Ollama 는 필요 없다.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def check():
    import ollama
    import src.answer as A

    calls = []

    def stub(**kw):
        calls.append(kw)
        return {"message": {"content": "(스텁: LLM 이 실제로 호출됨)"}}

    ollama.chat = stub                      # 모듈 속성 교체 → answer.py 가 이걸 쓴다

    results = []

    def case(label, fn, want_withheld, want_calls):
        calls.clear()
        out = fn()
        text = out[0]
        withheld = (text == A.NO_EVIDENCE)
        ok = withheld == want_withheld and len(calls) == want_calls
        state = "유보(생성 안 함)" if withheld else "생성함"
        print(f"  {'✅' if ok else '❌'} {label}")
        print(f"      → {state}, LLM 호출 {len(calls)}회 (기대 {want_calls}회)")
        results.append(ok)

    print(f"임계값 {A.CONF_THRESHOLD} 기준\n")

    print("[근거 부족 → 생성 건너뜀]")
    case("회사에 헬스장이 있나요? (유사도 0.48)",
         lambda: A.answer("회사에 헬스장이 있나요?"), True, 0)
    case("스톡옵션 언제 받아? (유사도 0.40)",
         lambda: A.answer_with_history("스톡옵션 언제 받아?", []), True, 0)

    print("\n[근거 충분 → 정상 생성]")
    case("연차 며칠 쓸 수 있어? (유사도 0.66)",
         lambda: A.answer("연차 며칠 쓸 수 있어?"), False, 1)
    case("제27조가 뭐야? (번호 조회, 정확 일치)",
         lambda: A.answer_with_history("제27조가 뭐야?", []), False, 1)

    # 후속질문은 condense_query 가 LLM 을 1회 쓴다. 가드가 걸려도 '생성'은 없어야 하므로
    # 호출은 재작성 1회에서 멈춰야 한다 (2회면 생성까지 간 것).
    print("\n[후속질문 — 재작성은 하되 생성은 막힘]")
    hist = [{"role": "user", "content": "연차 며칠?"},
            {"role": "assistant", "content": "15일입니다."}]
    calls.clear()
    text, hits, sq = A.answer_with_history("헬스장은 어때?", hist)
    withheld = (text == A.NO_EVIDENCE)
    ok = withheld and len(calls) == 1
    print(f"  {'✅' if ok else '❌'} 재작성 1회만 호출되고 생성은 안 됨")
    print(f"      → {'유보' if withheld else '생성함'}, LLM 호출 {len(calls)}회 (기대 1회)")
    results.append(ok)

    print(f"\n{sum(results)}/{len(results)} 통과 —",
          "✅ 신뢰도 가드가 생성을 실제로 차단함" if all(results) else "⚠️ 위 ❌ 지점 확인")


if __name__ == "__main__":
    check()
