"""서버 기동 시 모델을 미리 적재한다 (F4).

첫 요청이 3.4초 걸리는 이유는 임베딩 모델(bge-m3) 로드가 요청 경로 안에서
일어나기 때문이다. 콜드 스타트 비용을 없애는 게 아니라 **서버 시작 시점으로
옮기는** 것이다. 그래서 '서버 시작이 얼마나 느려지는가'를 함께 재야 한다.

Ollama 는 기본적으로 일정 시간 뒤 모델을 메모리에서 내린다.
keep_alive 를 주면 유지되지만 그만큼 VRAM 을 계속 점유한다.
"""
import os
import sys
import time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KEEP_ALIVE = "30m"      # Ollama 가 모델을 메모리에 유지하는 시간


@dataclass
class WarmupReport:
    steps: dict = field(default_factory=dict)

    @property
    def total_sec(self) -> float:
        return sum(self.steps.values())

    def show(self):
        for k, v in self.steps.items():
            print(f"  {k:<16} {v:>6.2f}s")
        print(f"  {'합계':<16} {self.total_sec:>6.2f}s")


def warm_all(stt=None, sample_wav: str = None) -> WarmupReport:
    """임베딩·LLM·STT 를 적재하고 더미 요청을 1회씩 돌린다."""
    rep = WarmupReport()

    # 1) 색인 + 임베딩 모델 — 첫 요청 지연의 주범
    t = time.perf_counter()
    from src.store import load_index, search
    chunks, vecs = load_index(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "index"))
    search("워밍업", chunks, vecs, k=1)          # 임베딩 모델이 여기서 로드된다
    rep.steps["임베딩+색인"] = time.perf_counter() - t

    # 2) LLM — keep_alive 로 메모리에 묶어둔다
    t = time.perf_counter()
    import ollama
    from src.answer import MODEL, OPTIONS
    ollama.chat(model=MODEL, options=OPTIONS, keep_alive=KEEP_ALIVE,
                messages=[{"role": "user", "content": "안녕"}])
    rep.steps["LLM"] = time.perf_counter() - t

    # 3) STT
    if stt is not None and sample_wav:
        t = time.perf_counter()
        stt.warmup(sample_wav)
        rep.steps["STT"] = time.perf_counter() - t

    return rep, chunks, vecs


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    from question_sets import EVAL
    from stt import STT
    from vocab import initial_prompt

    D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")
    sample = os.path.join(D, f"{EVAL[0][0]}.wav")

    t = time.perf_counter()
    stt = STT("small", initial_prompt=initial_prompt())
    stt_load = time.perf_counter() - t

    print("서버 시작 워밍업")
    rep, chunks, vecs = warm_all(stt, sample)
    rep.steps["STT 모델 로드"] = stt_load
    rep.show()
    print(f"\n  Ollama keep_alive = {KEEP_ALIVE}")
