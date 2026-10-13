"""음성 질의 HTTP API (실행: python voice/api.py)

Streamlit, CLI, MCP 에 이은 **네 번째 표면**이다. 판정은 기존 judge_evidence()
를 그대로 공유한다 — 판정은 공통, 채널만 개별.

한계 (의도적으로 범위 밖):
  단일 워커(uvicorn 기본)로 띄우므로 **동시 요청은 순차 처리된다.**
  모델이 GPU 를 점유하는 구조라 워커를 늘려도 VRAM 이 그만큼 더 든다.
  동시 접속·부하는 이번 범위가 아니다 (docs/stt-plan.md 2장).
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from src.answer import (CONF_THRESHOLD, MIN_SUPPORT, NO_EVIDENCE, SUPPORT_FLOOR,
                        answer_with_history, judge_evidence)
from src.audit import log_turn
from src.store import EXACT_SCORE, search
from stt import STT
from vocab import initial_prompt
from warmup import KEEP_ALIVE, warm_all

app = FastAPI(title="규정봇 음성 질의 API")
_state = {}


class Article(BaseModel):
    article_no: int
    article_title: str
    chapter: str
    similarity: float | None = None
    match: str | None = None


class VoiceAnswer(BaseModel):
    stt_text_raw: str
    stt_text: str
    answer: str
    has_evidence: bool
    passed_by: str | None
    top_similarity: float | None
    support_count: int
    threshold: float = CONF_THRESHOLD
    support_floor: float = SUPPORT_FLOOR
    min_support: int = MIN_SUPPORT
    articles: list[Article]
    timings_ms: dict


@app.on_event("startup")
def startup():
    """모델을 미리 적재한다. 시작이 느려지는 대신 첫 요청이 빨라진다."""
    t = time.perf_counter()
    stt = STT("small", initial_prompt=initial_prompt())
    rep, chunks, vecs = warm_all(stt, _sample_wav())
    _state.update(stt=stt, chunks=chunks, vecs=vecs)
    print(f"[startup] 워밍업 {time.perf_counter() - t:.1f}s "
          f"(keep_alive={KEEP_ALIVE})")


def _sample_wav():
    from question_sets import EVAL
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "recordings", f"{EVAL[0][0]}.wav")


@app.get("/health")
def health():
    return {"ready": bool(_state), "threshold": CONF_THRESHOLD,
            "support_floor": SUPPORT_FLOOR, "min_support": MIN_SUPPORT}


@app.post("/ask-voice", response_model=VoiceAnswer)
async def ask_voice(file: UploadFile = File(...)):
    t_all = time.perf_counter()
    stt, chunks, vecs = _state["stt"], _state["chunks"], _state["vecs"]

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(await file.read())
        path = f.name
    try:
        r = stt.transcribe(path)

        t = time.perf_counter()
        hits = search(r.text, chunks, vecs, k=3)
        retrieval_ms = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        v = judge_evidence(hits)
        guard_ms = (time.perf_counter() - t) * 1000

        t = time.perf_counter()
        answer, _, _ = answer_with_history(r.text, [])
        llm_ms = (time.perf_counter() - t) * 1000

        exact = v["passed_by"] == "exact"
        arts = [Article(article_no=c["article_no"], article_title=c["article_title"],
                        chapter=c["chapter"],
                        **({"match": "exact"} if s == EXACT_SCORE
                           else {"similarity": round(float(s), 3)}))
                # 근거가 부족하면 조문 본문을 애초에 담지 않는다 (MCP 와 같은 원칙)
                for c, s in hits]

        timings = {"audio_sec": round(r.audio_sec, 2),
                   "stt": round(r.stt_ms, 1),
                   "normalize": round(r.normalize_ms, 2),
                   "retrieval": round(retrieval_ms, 1),
                   "guard": round(guard_ms, 2),
                   "llm": round(llm_ms, 1),
                   "total": round((time.perf_counter() - t_all) * 1000, 1)}

        log_turn(r.text, answer, hits)
        return VoiceAnswer(
            stt_text_raw=r.text_raw, stt_text=r.text, answer=answer,
            has_evidence=v["ok"], passed_by=v["passed_by"],
            top_similarity=None if exact else round(v["top"], 3),
            support_count=v["support"], articles=arts, timings_ms=timings)
    finally:
        os.unlink(path)


if __name__ == "__main__":
    import uvicorn
    # workers=1: 모델이 GPU 를 점유하므로 워커를 늘리면 VRAM 이 배로 든다.
    # 동시 요청은 순차 처리된다 — 이번 범위에서 의도한 한계다.
    uvicorn.run(app, host="127.0.0.1", port=8000, workers=1)
