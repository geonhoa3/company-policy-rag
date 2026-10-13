"""콜드 스타트 베이스라인 재측정 (실행: python voice/measure_coldstart.py [--warm])

v1 기획서는 "콜드 스타트 2.2초"를 썼지만, 그 값은 콜드 상태에서 18건 생성의
'평균'이지 첫 요청 하나의 응답 시간이 아니었다. 그래서 절차를 정해 다시 잰다.

  절차: Ollama 모델 언로드 + 새 파이썬 프로세스 → 첫 요청 1회

--warm 을 주면 워밍업을 먼저 돌린 뒤 첫 요청을 잰다.
서버 시작 시간이 얼마나 늘어나는지도 함께 기록한다 — 콜드 비용을 없애는 게
아니라 시작 시점으로 옮기는 것이므로, 둘을 같이 봐야 트레이드오프가 보인다.
"""
import io
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

OLLAMA = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")


def vram_mb():
    """현재 GPU 메모리 사용량 (MB)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:
        return -1


def ollama_loaded():
    """ollama ps 가 보고하는 적재 모델."""
    try:
        out = subprocess.run([OLLAMA, "ps"], capture_output=True, text=True, timeout=15)
        lines = [l for l in out.stdout.splitlines()[1:] if l.strip()]
        return lines
    except Exception:
        return []


def main():
    warm = "--warm" in sys.argv
    print(f"모드: {'워밍업 후' if warm else '콜드 (워밍업 없음)'}")
    print(f"시작 시점 VRAM {vram_mb()}MB\n")

    from question_sets import EVAL
    from stt import STT
    from vocab import initial_prompt

    sample = os.path.join(D, f"{EVAL[0][0]}.wav")

    # ---- 서버 시작 구간 ----
    t_start = time.perf_counter()
    stt = STT("small", initial_prompt=initial_prompt())
    if warm:
        from warmup import warm_all
        rep, chunks, vecs = warm_all(stt, sample)
    else:
        from src.store import load_index
        chunks, vecs = load_index(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "index"))
        rep = None
    startup = time.perf_counter() - t_start

    vram_after_start = vram_mb()

    # ---- 첫 요청 ----
    from src.answer import answer_with_history
    from src.store import search

    t0 = time.perf_counter()
    r = stt.transcribe(sample)
    stt_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    search(r.text, chunks, vecs, k=3)
    retrieval_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    answer_with_history(r.text, [])
    llm_ms = (time.perf_counter() - t0) * 1000

    first = stt_ms + retrieval_ms + llm_ms

    print(f"서버 시작        {startup:>7.2f}s")
    if rep:
        for k, v in rep.steps.items():
            print(f"    {k:<14} {v:>6.2f}s")
    print()
    print(f"첫 요청          {first/1000:>7.2f}s")
    print(f"    STT          {stt_ms:>7.0f}ms")
    print(f"    검색         {retrieval_ms:>7.0f}ms")
    print(f"    LLM          {llm_ms:>7.0f}ms")
    print()
    print(f"VRAM  시작 후 {vram_after_start}MB  /  첫 요청 후 {vram_mb()}MB")
    for line in ollama_loaded():
        print(f"  ollama ps: {line}")


if __name__ == "__main__":
    main()
