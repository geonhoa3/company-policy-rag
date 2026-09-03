# app.py — Streamlit 웹 UI (실행: streamlit run app.py)
import streamlit as st
from src.answer import answer_with_history
from src.leave import leave_days, extract_hire_date
from src.audit import log_turn

CONF_THRESHOLD = 0.5   # 최고 유사도가 이보다 낮으면 신뢰도 경고

st.set_page_config(page_title="회사 규정 QA", page_icon="📖")
st.title("📖 회사 규정 QA")
st.caption("취업규칙에 대해 물어보세요. 규정에 없는 내용은 답하지 않습니다.")

# 사이드바: 입사일 입력 → 코드가 연차를 정확히 계산 (LLM 산수 대체)
leave_fact = ""
with st.sidebar:
    st.subheader("📅 연차 계산 (선택)")
    hire = st.date_input("입사일", value=None, format="YYYY-MM-DD")
    if hire:
        r = leave_days(hire)
        st.metric("현재 연차", f"{r['days']}일")
        st.caption(r["basis"])
        # 이 사실을 챗 답변의 근거로 주입 → LLM은 계산 안 하고 이 숫자만 사용
        leave_fact = f"입사일 {hire} 기준, {r['basis']}, 연차 {r['days']}일."

# 1) 대화 기억 — Streamlit은 매 입력마다 스크립트를 통째로 재실행하므로
#    일반 변수로는 히스토리가 날아간다. session_state에 담아야 유지됨.
if "history" not in st.session_state:
    st.session_state.history = []

# 2) 이전 대화 다시 그리기 (재실행되니 매번 새로 렌더)
for m in st.session_state.history:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# 3) 입력창 + 처리
if q := st.chat_input("예: 연차 며칠 쓸 수 있어?"):
    with st.chat_message("user"):
        st.markdown(q)

    # 사이드바 입사일이 없으면, 채팅 문장에서 날짜를 뽑아 코드 계산 시도
    turn_fact = leave_fact
    if not turn_fact:
        hire_in_text = extract_hire_date(q)
        if hire_in_text:
            r = leave_days(hire_in_text)
            turn_fact = f"입사일 {hire_in_text} 기준, {r['basis']}, 연차 {r['days']}일."

    with st.chat_message("assistant"):
        with st.spinner("규정 검색 중..."):
            text, hits, sq = answer_with_history(q, st.session_state.history, extra_context=turn_fact)

        top_score = hits[0][1] if hits else 0.0

        # 1) 신뢰도 경고 — 근거가 약하면 맹신 금지
        if top_score < CONF_THRESHOLD:
            st.warning("⚠️ 규정에서 명확한 근거를 찾지 못했을 수 있습니다. 아래 원문과 대조해 확인하세요.")

        st.markdown(text)

        # 2) 출처 원문 — 펼쳐서 직접 검증
        with st.expander(f"📎 근거 조항 원문 (최고 유사도 {top_score:.2f})"):
            for c, score in hits:
                st.markdown(f"**{c['chapter']} · 제{c['article_no']}조 ({c['article_title']})** — 유사도 {score:.2f}")
                st.text(c["text"])
        if sq != q:
            st.caption(f"검색용 재작성: {sq}")

        # 3) 감사 로그 — 모든 Q&A 기록 (책임 추적)
        log_turn(q, text, hits, extra_fact=turn_fact)

    # 이번 턴 저장 (원 질문 그대로 — 자연스러운 대화 유지)
    st.session_state.history.append({"role": "user", "content": q})
    st.session_state.history.append({"role": "assistant", "content": text})
