"""음성 전용 파이프라인 — 구간별 데드라인과 대체 경로 (F3).

기존 `answer_with_history()` 는 **건드리지 않는다.** 텍스트 경로가 바뀌면
30문항 + 홀드아웃 10문항 평가가 무효가 된다 (docs/stt-plan.md 3-4).

데드라인을 거는 방법:
  ollama.chat() 은 블로킹이라 중간에 끊을 수 없다. stream=True 로 토큰을
  받으면서 시간을 재고, 넘기면 제너레이터를 닫아 연결을 끊는다.
  닫지 않으면 서버가 계속 생성해 GPU 를 쓴다.

데드라인을 넘긴 부분 답변은 **버린다.** 중간에 잘린 답은 틀린 답이 될 수 있어
"불확실하면 지어내지 않는다" 는 원칙과 맞지 않는다. 대신 근거 조항 원문을 준다.
"""
import os
import sys
import time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
import ollama

from src.answer import (MODEL, NO_EVIDENCE, OPTIONS, _system_with_date,
                        judge_evidence)
from src.store import search

# 지연 예산 v3 (docs/stt-plan.md F3) — Day 1 실측으로 재배분한 값
BUDGET = {"stt": 0.6, "retrieval": 0.1, "llm": 2.0}

# STT 신뢰도 하한. 이보다 낮거나 무음 확률이 높으면 재질문한다
CONNECT_TIMEOUT = 0.3      # LLM 서버에 닿는 데까지만. 생성 시간과 별개다

MIN_LOGPROB = -1.0
MAX_NO_SPEECH = 0.6

RETRY_MSG = "다시 한 번 말씀해 주시겠어요?"
CHECK_LATER_MSG = "확인 후 다시 안내드리겠습니다. 상담원 연결을 도와드릴까요?"


@dataclass
class VoiceResult:
    answer: str
    fallback: str | None = None          # 대체 경로 종류, 정상이면 None
    has_evidence: bool = False
    passed_by: str | None = None
    hits: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)

    @property
    def fell_back(self) -> bool:
        return self.fallback is not None


DELAYED_LEAD = "답변 생성이 지연되어 근거 조항 원문을 먼저 안내드립니다."
UNAVAILABLE_LEAD = "답변 생성을 할 수 없어 근거 조항 원문을 안내드립니다."


def _evidence_text(hits, lead: str = DELAYED_LEAD) -> str:
    """생성 대신 돌려줄 근거 조항 원문.

    머리말을 경로별로 나눈다. 연결 실패에 "지연되어" 라고 하면 기다리면 답이
    온다는 뜻이 되고, "먼저" 는 뒤에 생성 답변이 따라온다는 뜻이 된다. 둘 다
    사실이 아니다.
    """
    body = "\n\n".join(c["text"] for c, _ in hits)
    return f"{lead}\n\n{body}"


class LLMDown(Exception):
    """LLM 서버에 닿지 못함 (지연과 구분해야 한다)."""


def _stream_with_deadline(messages, deadline: float):
    """스트리밍하며 데드라인을 감시한다.

    반환: (완성 텍스트 또는 None, ttft_ms, 경과초)
    데드라인을 넘기면 제너레이터를 닫고 None 을 돌려준다.

    데드라인 검사만으로는 부족하다. 검사는 '청크가 도착할 때' 돌기 때문에,
    서버가 아무것도 보내지 않으면 첫 토큰을 무한정 기다린다. 실측에서 Ollama 를
    내렸을 때 2초 예산인데 5.02초가 걸렸다. 그래서 클라이언트에 타임아웃을 걸어
    첫 토큰까지의 시간도 덮는다.
    """
    t0 = time.perf_counter()
    ttft = None
    parts = []
    # 연결 타임아웃을 생성 예산 전체로 잡으면, 서버가 죽었을 때도 2초를 다 기다린다.
    # 로컬 Ollama 연결은 밀리초면 되므로 연결만 따로 짧게 끊는다.
    # 읽기 타임아웃은 생성 예산 그대로 둔다 (첫 토큰이 늦는 '지연' 케이스를 덮기 위해).
    client = ollama.Client(timeout=httpx.Timeout(deadline, connect=CONNECT_TIMEOUT))
    try:
        stream = client.chat(model=MODEL, options=OPTIONS,
                             messages=messages, stream=True)
    except Exception as e:
        raise LLMDown(str(e)) from e

    try:
        for chunk in stream:
            if ttft is None:
                ttft = (time.perf_counter() - t0) * 1000
            parts.append(chunk["message"]["content"])
            if time.perf_counter() - t0 > deadline:
                return None, ttft, time.perf_counter() - t0      # 부분 답변은 버린다
    except (httpx.ConnectError, httpx.ConnectTimeout) as e:
        # 서버에 닿지 못함 → 장애. ConnectTimeout 은 TimeoutException 의 하위라
        # 아래 지연 분기보다 먼저 잡아야 한다.
        raise LLMDown(str(e)) from e
    except httpx.TimeoutException:
        # 연결은 됐는데 응답이 늦은 경우 → 장애가 아니라 지연
        return None, ttft, time.perf_counter() - t0
    except Exception as e:
        raise LLMDown(str(e)) from e
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()                      # 연결을 끊어 서버 생성도 멈춘다
    return "".join(parts).strip(), ttft, time.perf_counter() - t0


def answer_voice(stt_result, chunks, vecs, k: int = 3,
                 budget: dict = None) -> VoiceResult:
    """음성 질의 한 건을 끝까지 처리한다."""
    b = {**BUDGET, **(budget or {})}
    t = {}

    # 1) STT 신뢰도 — 못 알아들었으면 되묻는다
    if (stt_result.avg_logprob < MIN_LOGPROB
            or stt_result.no_speech_prob > MAX_NO_SPEECH):
        return VoiceResult(answer=RETRY_MSG, fallback="stt_low_confidence",
                           timings={"stt": stt_result.stt_ms})

    t["stt"] = stt_result.stt_ms

    # 2) 검색 — 느리면 생성으로 넘어가지 않는다
    t0 = time.perf_counter()
    try:
        hits = search(stt_result.text, chunks, vecs, k=k)
    except Exception:
        return VoiceResult(answer=CHECK_LATER_MSG, fallback="retrieval_error", timings=t)
    t["retrieval"] = (time.perf_counter() - t0) * 1000
    if t["retrieval"] / 1000 > b["retrieval"]:
        return VoiceResult(answer=CHECK_LATER_MSG, fallback="retrieval_timeout",
                           hits=hits, timings=t)

    # 3) 가드 — 근거가 없으면 LLM 을 아예 부르지 않는다 (기존 원칙)
    t0 = time.perf_counter()
    v = judge_evidence(hits)
    t["guard"] = (time.perf_counter() - t0) * 1000
    if not v["ok"]:
        return VoiceResult(answer=NO_EVIDENCE, has_evidence=False,
                           passed_by=None, hits=hits, timings=t)

    # 4) 생성 — 데드라인을 넘기면 근거 원문으로 대체
    context = "\n\n".join(c["text"] for c, _ in hits)
    messages = [{"role": "system", "content": _system_with_date()},
                {"role": "user", "content": f"규정:\n{context}\n\n질문: {stt_result.text}"}]
    t0 = time.perf_counter()
    try:
        text, ttft, elapsed = _stream_with_deadline(messages, b["llm"])
    except LLMDown:
        t["llm"] = (time.perf_counter() - t0) * 1000
        return VoiceResult(answer=_evidence_text(hits, UNAVAILABLE_LEAD),
                           fallback="llm_error",
                           has_evidence=True, passed_by=v["passed_by"],
                           hits=hits, timings=t)

    t["ttft"] = ttft
    t["llm"] = elapsed * 1000
    if text is None:
        return VoiceResult(answer=_evidence_text(hits), fallback="llm_timeout",
                           has_evidence=True, passed_by=v["passed_by"],
                           hits=hits, timings=t)

    return VoiceResult(answer=text, has_evidence=True, passed_by=v["passed_by"],
                       hits=hits, timings=t)
