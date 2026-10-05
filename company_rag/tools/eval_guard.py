"""신뢰도 가드 평가 — 라벨링된 질문셋으로 오거부·오답변을 센다.

자가 검증(check_*.py)이 '기능이 동작하는가'를 보는 반면, 이 스크립트는
'임계값이 옳은가'를 숫자로 따진다. 두 지표가 모두 0이어야 한다.

  오거부(false refusal) : 규정에 있는데 답을 거부한 수
  오답변(false answer)  : 규정에 없는데 답을 지어낸 수

실행:  python tools/eval_guard.py        결과 표 출력
       python tools/eval_guard.py --md   docs/evaluation.md 용 마크다운 출력
※ 임베딩 + Ollama 가 모두 필요하다 (생성 경로를 실제로 타기 때문).
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
BASE = os.path.join(os.path.dirname(__file__), "..")

# (질문, 규정에 있는가, 기대 근거 조항)
QUESTIONS = [
    ("무단결근 며칠이면 징계 받아?",        True,  27),
    ("육아휴직 얼마나 쓸 수 있어?",         True,  23),
    ("수습기간 임금은 몇 퍼센트야?",         True,   5),
    ("결혼하면 휴가 며칠 나와?",            True,  13),
    ("연차 며칠 쓸 수 있어?",              True,  12),
    ("퇴직하려면 어떻게 해야 해?",           True,  24),
    ("야간근로 수당 가산율이 어떻게 돼?",      True,   9),
    ("겸직해도 되나요?",                   True,  21),
    ("병가는 며칠까지 쓸 수 있어?",          True,  14),
    ("재택근무 신청은 며칠 전에 해야 해?",     True,  10),
    ("제3조가 뭐야?",                     True,   3),
    ("제27조가 뭐야?",                    True,  27),
    ("반려동물 동반출근 가능해?",            False, None),
    ("통근버스 운행하나요?",                False, None),
    ("사택이나 기숙사 제공하나요?",           False, None),
    ("주차비 지원해주나요?",                False, None),
    ("생일에 선물 주나요?",                 False, None),
    ("사내 헬스장 이용료 얼마야?",            False, None),
    ("자녀 학자금 지원되나요?",              False, None),
    ("스톡옵션 언제 받아?",                 False, None),
]


def run():
    import numpy as np
    from src.store import load_index, lookup_by_article_no
    from src.embedder import embed_texts
    from src.answer import answer_with_history, CONF_THRESHOLD, NO_EVIDENCE

    chunks, vecs = load_index(os.path.join(BASE, "index"))
    rows = []
    for q, inside, want in QUESTIONS:
        # 라우팅과 무관한 '순수 벡터 점수' — 번호 질문이 왜 임계값으로는
        # 구제되지 않는지 보여주기 위해 따로 잰다
        vscore = float(np.max(vecs @ embed_texts([q])[0]))
        routed = lookup_by_article_no(q, chunks) is not None

        t0 = time.perf_counter()
        text, hits, _ = answer_with_history(q, [])
        sec = time.perf_counter() - t0

        refused = (text == NO_EVIDENCE)
        rows.append(dict(
            q=q, inside=inside, want=want, vscore=vscore, routed=routed,
            refused=refused, sec=sec,
            cited=hits[0][0]["article_no"] if hits else None,
            path=("정규식 조회" if routed else
                  "임계값 미달 → 거부" if refused else "임계값 통과 → 생성"),
        ))
    return rows, CONF_THRESHOLD


def summarize(rows, thr):
    import numpy as np
    inside = [r for r in rows if r["inside"]]
    outside = [r for r in rows if not r["inside"]]
    answered = [r for r in inside if not r["refused"]]
    return dict(
        total=len(rows), n_in=len(inside), n_out=len(outside),
        false_refuse=[r for r in inside if r["refused"]],
        false_answer=[r for r in outside if not r["refused"]],
        cite_ok=sum(1 for r in answered if r["cited"] == r["want"]),
        n_answered=len(answered),
        t_gen=float(np.mean([r["sec"] for r in rows if not r["refused"]])),
        t_ref=float(np.mean([r["sec"] for r in rows if r["refused"]])),
        in_lo=min(r["vscore"] for r in inside if not r["routed"]),
        in_hi=max(r["vscore"] for r in inside if not r["routed"]),
        out_lo=min(r["vscore"] for r in outside),
        out_hi=max(r["vscore"] for r in outside),
        thr=thr,
    )


def main():
    md = "--md" in sys.argv
    rows, thr = run()
    s = summarize(rows, thr)

    if md:
        for label, want in [("규정 안", True), ("규정 밖", False)]:
            print(f"\n**{label}**\n")
            print("| 질문 | 벡터 유사도 | 처리 경로 | 결과 |")
            print("|---|---:|---|---|")
            for r in [x for x in rows if x["inside"] is want]:
                res = "근거 없음" if r["refused"] else f"정상 답변 (제{r['cited']}조)"
                print(f"| {r['q']} | {r['vscore']:.3f} | {r['path']} | {res} |")
    else:
        for r in rows:
            ok = (not r["refused"]) if r["inside"] else r["refused"]
            print(f"{'✅' if ok else '❌'} {r['sec']:5.2f}s  v={r['vscore']:.3f}  "
                  f"{r['path']:<18} {r['q']}")

    print(f"\n임계값 {s['thr']}")
    print(f"전체 {s['total']}문항 (규정 안 {s['n_in']} / 규정 밖 {s['n_out']})")
    print(f"오거부(규정 안인데 거부): {len(s['false_refuse'])}")
    print(f"오답변(규정 밖인데 답변): {len(s['false_answer'])}")
    print(f"근거 조항 적중: {s['cite_ok']}/{s['n_answered']}")
    print(f"응답시간 생성 {s['t_gen']:.2f}s / 거부 {s['t_ref']:.2f}s "
          f"({s['t_gen']/s['t_ref']:.0f}배)")
    print(f"벡터점수 규정 안(내용) {s['in_lo']:.3f}~{s['in_hi']:.3f} / "
          f"규정 밖 {s['out_lo']:.3f}~{s['out_hi']:.3f}")
    print(f"임계값 여유 — 밖 {s['thr']-s['out_hi']:+.3f} / 안 {s['in_lo']-s['thr']:+.3f}")
    for r in s["false_refuse"]:
        print("  [오거부]", r["q"], f"{r['vscore']:.3f}")
    for r in s["false_answer"]:
        print("  [오답변]", r["q"], f"{r['vscore']:.3f}")


if __name__ == "__main__":
    main()
