"""장애 주입 테스트 (실행: python voice/fault_injection.py)

워밍업을 **먼저 끝낸 뒤** 주입한다. 콜드 상태에서 Ollama 를 끄면
"느려서 대체됐는지, 죽어서 대체됐는지" 구분할 수 없기 때문이다.

시나리오마다 세 가지를 기록한다.
  대체 응답 종류 / 대체까지 걸린 시간 / 해당 구간 예산 대비 초과 여부
"""
import io
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import numpy as np
import soundfile as sf

import pipeline
from pipeline import BUDGET, answer_voice
from question_sets import EVAL
from stt import STT
from vocab import initial_prompt
from warmup import warm_all

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
QUESTION = "eval05"          # "연차 며칠 쓸 수 있어?" — 정상이면 생성까지 가는 질문


def silent_wav(path, sec=3.0, sr=16000):
    sf.write(path, (0.0005 * np.random.randn(int(sr * sec))).astype("float32"), sr)
    return path


def run():
    stt = STT("small", initial_prompt=initial_prompt())
    print("워밍업 중...")
    rep, chunks, vecs = warm_all(stt, os.path.join(D, f"{QUESTION}.wav"))
    print(f"워밍업 완료 {rep.total_sec:.1f}s — 이 상태에서 장애를 주입한다\n")

    wav = os.path.join(D, f"{QUESTION}.wav")
    base_stt = stt.transcribe(wav)
    results = []

    def record(name, budget_key, fn, expect):
        t0 = time.perf_counter()
        r = fn()
        sec = time.perf_counter() - t0
        limit = BUDGET.get(budget_key, 0) + 0.2        # 구간 예산 + 0.2초
        results.append(dict(name=name, fallback=r.fallback, expect=expect,
                            sec=sec, limit=limit, ok=r.fallback == expect,
                            within=sec <= limit, answer=r.answer))
        mark = "✅" if r.fallback == expect else "❌"
        print(f"{mark} {name}")
        print(f"     대체 경로  {r.fallback}  (기대 {expect})")
        print(f"     소요       {sec:.2f}s   예산+0.2s = {limit:.2f}s  "
              f"{'이내' if sec <= limit else '초과'}")
        print(f"     응답       {r.answer.strip()[:62]}")
        print()

    # 1) 정상 (기준선) — 장애 없이도 대체가 안 걸리는지 먼저 확인
    record("정상 동작 (기준선)", "llm",
           lambda: answer_voice(base_stt, chunks, vecs), None)

    # 2) LLM 지연 — 느린 스트림을 흘려보내 '실제' 데드라인 로직을 태운다.
    #    _stream_with_deadline 을 통째로 바꿔치면 검증하려는 코드를 건너뛰게 된다.
    class _SlowClient:
        def __init__(self, timeout=None):
            self.timeout = timeout
        def chat(self, **kw):
            def gen():
                for _ in range(100):
                    time.sleep(0.25)
                    yield {"message": {"content": "가"}}
            return gen()

    orig_client = pipeline.ollama.Client
    pipeline.ollama.Client = _SlowClient
    record("LLM 지연 (데드라인 초과)", "llm",
           lambda: answer_voice(base_stt, chunks, vecs), "llm_timeout")
    pipeline.ollama.Client = orig_client

    # 3) 검색 지연
    orig_search = pipeline.search
    def slow_search(*a, **kw):
        time.sleep(BUDGET["retrieval"] + 0.15)
        return orig_search(*a, **kw)
    pipeline.search = slow_search
    record("검색 지연", "retrieval",
           lambda: answer_voice(base_stt, chunks, vecs), "retrieval_timeout")
    pipeline.search = orig_search

    # 4) 무음 입력
    quiet = silent_wav(os.path.join(D, "_silence_tmp.wav"))
    try:
        qr = stt.transcribe(quiet)
        record("무음·잡음 입력", "stt",
               lambda: answer_voice(qr, chunks, vecs), "stt_low_confidence")
    finally:
        os.remove(quiet)

    # 5) LLM 서버 다운 — 닿지 않는 주소로 보낸다.
    #    Ollama Desktop 은 프로세스를 죽여도 자동 재시작해서, 실제로 내리면
    #    '다운'이 아니라 '모델 재적재 중인 느린 서버'가 된다. 그러면 장애와 지연을
    #    구분할 수 없다. 연결 거부는 다운 상태가 만드는 것과 같은 조건이고 재현도 된다.
    def _dead_client(timeout=None):
        return orig_client(host="http://127.0.0.1:1", timeout=timeout)
    pipeline.ollama.Client = _dead_client
    record("LLM 서버 다운 (연결 거부)", "llm",
           lambda: answer_voice(base_stt, chunks, vecs), "llm_error")
    pipeline.ollama.Client = orig_client
    # ---- 요약 ----
    print("=" * 70)
    inject = [r for r in results if r["expect"] is not None]
    ok = sum(1 for r in inject if r["ok"])
    within = sum(1 for r in inject if r["within"])
    print(f"장애 주입 {ok}/{len(inject)} 대체 응답 성공")
    print(f"예산+0.2s 이내 {within}/{len(inject)}")
    print()
    print(f"  {'시나리오':<22}{'대체 경로':<22}{'소요':>8}{'한도':>8}")
    for r in results:
        print(f"  {r['name']:<22}{str(r['fallback']):<22}{r['sec']:>7.2f}s{r['limit']:>7.2f}s")


if __name__ == "__main__":
    run()
