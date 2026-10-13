"""음성 평가 실행 (실행: python voice/run_eval.py)

eval 40문항  : 음성 입력이 텍스트 입력과 같은 판정을 내리는지
number 15문항: 조항 번호 인식률 (숫자 정규화 전/후)

텍스트 기준선은 같은 질문 원문을 그대로 파이프라인에 넣어 그 자리에서 구한다.
가드(judge_evidence)와 임계값은 건드리지 않는다 — 음성에 맞춰 바꾸면
기존 평가가 무효가 된다 (docs/stt-plan.md 2장).
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from metrics import cer, corpus_cer
from normalize import normalize_article_numbers
from question_sets import EVAL, NUMBER, NUMBER_NEW
from stt import STT
from vocab import initial_prompt

from src.answer import NO_EVIDENCE, answer_with_history, judge_evidence
from src.store import ARTICLE_Q_RE, load_index, lookup_by_article_no, search

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from eval_guard import HOLDOUT, QUESTIONS

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LABELS = {q: (inside, want) for q, inside, want in QUESTIONS + HOLDOUT}


def run_text(question, chunks, vecs):
    """텍스트 입력 기준선."""
    hits = search(question, chunks, vecs, k=3)
    v = judge_evidence(hits)
    return v["ok"], (hits[0][0]["article_no"] if hits else None)


def main():
    chunks, vecs = load_index(os.path.join(BASE, "index"))
    use_prompt = "--prompt" in sys.argv
    stt = STT("small", initial_prompt=initial_prompt() if use_prompt else None)
    print(f"initial_prompt: {'사용' if use_prompt else '미사용'}")
    stt.warmup(os.path.join(D, f"{EVAL[0][0]}.wav"))

    # ---------- eval 40문항 ----------
    rows = []
    for qid, question in EVAL:
        r = stt.transcribe(os.path.join(D, f"{qid}.wav"))

        t0 = time.perf_counter()
        hits = search(r.text, chunks, vecs, k=3)
        retrieval_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        v = judge_evidence(hits)
        guard_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        text, _, _ = answer_with_history(r.text, [])
        llm_ms = (time.perf_counter() - t0) * 1000
        # 가드가 막은 것과 LLM 이 스스로 "규정에 없다"고 답한 것을 구분한다.
        # 둘 다 사용자에게는 거부로 보이지만, 안전장치가 어디서 작동했는지가 다르다.
        guard_blocked = text == NO_EVIDENCE
        llm_refused = (not guard_blocked) and ("규정에 없" in text)
        refused = guard_blocked or llm_refused

        txt_ok, txt_cited = run_text(question, chunks, vecs)
        inside, want = LABELS[question]

        rows.append(dict(
            qid=qid, question=question, stt_raw=r.text_raw, stt=r.text,
            cer=cer(question, r.text_raw), inside=inside, want=want,
            voice_ok=not refused, text_ok=txt_ok,
            guard_passed=not guard_blocked, llm_refused=llm_refused, answer=text,
            cited=hits[0][0]["article_no"] if hits else None, text_cited=txt_cited,
            audio_sec=r.audio_sec, stt_ms=r.stt_ms, normalize_ms=r.normalize_ms,
            retrieval_ms=retrieval_ms, guard_ms=guard_ms, llm_ms=llm_ms,
            total_ms=r.stt_ms + r.normalize_ms + retrieval_ms + guard_ms + llm_ms,
            rtf=r.rtf, passed_by=v["passed_by"],
        ))

    # ---------- 번호 세트: 설계 15 + 신규 5 ----------
    # 설계 세트는 정규화 규칙을 만들 때 본 데이터다. 거기서만 좋아지면
    # 그 15개에 맞춘 것일 수 있어, 규칙 설계에 쓰지 않은 5문항으로 따로 본다.
    nrows = []
    for setname, items in (("설계", NUMBER), ("신규", NUMBER_NEW)):
        for qid, question in items:
            if not os.path.exists(os.path.join(D, f"{qid}.wav")):
                continue
            r = stt.transcribe(os.path.join(D, f"{qid}.wav"))
            want_no = int(ARTICLE_Q_RE.search(question).group(1))

            def got_no(t):
                m = ARTICLE_Q_RE.search(t)
                return int(m.group(1)) if m else None

            nrows.append(dict(setname=setname, qid=qid, question=question,
                              raw=r.text_raw, norm=r.text, want=want_no,
                              before=got_no(r.text_raw), after=got_no(r.text),
                              routed=lookup_by_article_no(r.text, chunks) is not None,
                              cer=cer(question, r.text_raw), rtf=r.rtf))

    report(rows, nrows)
    suffix = "_prompt" if use_prompt else ""
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"eval_result{suffix}.json")
    json.dump({"eval": rows, "number": nrows}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\n상세 결과 저장: {out}")


def pct(n, d):
    return f"{n}/{d}" + (f" ({n/d:.0%})" if d else "")


def report(rows, nrows):
    print("=" * 78)
    print("eval 40문항 — 음성 입력 vs 텍스트 입력\n")

    mismatch = [r for r in rows if r["voice_ok"] != r["text_ok"]]
    false_refuse = [r for r in rows if r["inside"] and not r["voice_ok"]]
    false_answer = [r for r in rows if not r["inside"] and r["voice_ok"]]
    inside_ans = [r for r in rows if r["inside"] and r["voice_ok"]]
    cite_ok = [r for r in inside_ans if r["cited"] == r["want"]]

    print(f"  CER (정규화 전 원본)        {corpus_cer([(r['question'], r['stt_raw']) for r in rows]):.1%}")
    print(f"  텍스트와 같은 판정          {pct(len(rows)-len(mismatch), len(rows))}")
    guard_bypass = [r for r in rows if not r["inside"] and r["guard_passed"]]
    print(f"  가드 통과 (규정 밖)         {len(guard_bypass)}건")
    print(f"  근거 없는 답변 (최종)       {len(false_answer)}건   ← 사용자에게 나간 답")
    for r in guard_bypass:
        where = "LLM 이 거부" if r["llm_refused"] else "⚠️ 답변 생성됨"
        print(f"      {r['qid']}  가드 통과 → {where}")
        print(f"         답변: {r['answer'].strip()[:60]}")
    print(f"  오거부 (규정 안)            {len(false_refuse)}건")
    print(f"  근거 조항 적중              {pct(len(cite_ok), len(inside_ans))}")

    if mismatch:
        print("\n  [판정이 갈린 문항]")
        for r in mismatch:
            print(f"    {r['qid']}  텍스트 {'답변' if r['text_ok'] else '거부'} → 음성 {'답변' if r['voice_ok'] else '거부'}")
            print(f"       정답 {r['question']}")
            print(f"       인식 {r['stt_raw']}")

    cite_miss = [r for r in inside_ans if r["cited"] != r["want"]]
    if cite_miss:
        print("\n  [근거 조항이 바뀐 문항]")
        for r in cite_miss:
            print(f"    {r['qid']}  기대 제{r['want']}조 → 음성 제{r['cited']}조 "
                  f"(텍스트는 제{r['text_cited']}조)")
            print(f"       인식 {r['stt_raw']}")

    print("\n" + "=" * 78)
    print("조항 번호 인식률 — 설계 세트 / 신규 세트\n")
    print(f"  {'세트':<6}{'정규화 전':>11}{'정규화 후':>11}{'CER':>9}")
    for setname in ("설계", "신규"):
        g = [r for r in nrows if r["setname"] == setname]
        if not g:
            continue
        b = sum(1 for r in g if r["before"] == r["want"])
        a = sum(1 for r in g if r["after"] == r["want"])
        print(f"  {setname:<6}{b:>7}/{len(g):<4}{a:>7}/{len(g):<4}"
              f"{corpus_cer([(r['question'], r['raw']) for r in g]):>8.1%}")
    before = sum(1 for r in nrows if r["before"] == r["want"])
    after = sum(1 for r in nrows if r["after"] == r["want"])
    print(f"  {'합계':<6}{before:>7}/{len(nrows):<4}{after:>7}/{len(nrows):<4}")

    bad = [r for r in nrows if r["after"] != r["want"]]
    if bad:
        print("\n  [번호를 놓친 문항]")
        for r in bad:
            print(f"    [{r['setname']}] {r['qid']}  기대 제{r['want']}조 → {r['after']}")
            print(f"       인식 {r['raw']}" + (f"  → 정규화 {r['norm']}" if r['norm'] != r['raw'] else ""))
    fixed = [r for r in nrows if r["before"] != r["want"] and r["after"] == r["want"]]
    if fixed:
        print("\n  [정규화가 살린 문항]")
        for r in fixed:
            print(f"    [{r['setname']}] {r['qid']}  {r['raw']} → {r['norm']}")

    print("\n" + "=" * 78)
    print("구간별 지연 (eval 40문항, 밀리초)\n")
    import statistics as st
    for name, key in [("STT", "stt_ms"), ("정규화", "normalize_ms"),
                      ("검색", "retrieval_ms"), ("가드", "guard_ms"),
                      ("LLM", "llm_ms"), ("전체", "total_ms")]:
        v = sorted(r[key] for r in rows)
        p50, p95 = st.median(v), v[int(len(v) * 0.95) - 1]
        print(f"  {name:<8} p50 {p50:>8.1f}   p95 {p95:>8.1f}   최대 {v[-1]:>8.1f}")
    rtf = [r["rtf"] for r in rows]
    print(f"\n  RTF      평균 {sum(rtf)/len(rtf):.3f}   최대 {max(rtf):.3f}")
    refused_rows = [r for r in rows if not r["voice_ok"]]
    if refused_rows:
        extra = [r["total_ms"] - r["stt_ms"] for r in refused_rows]
        print(f"  거부 경로 STT 이후 추가 시간   p50 {st.median(extra):.1f}ms  최대 {max(extra):.1f}ms")


if __name__ == "__main__":
    main()
