"""faster-whisper 로컬 STT.

외부 STT API 를 쓰지 않는 이유는 규정봇의 핵심 제약 때문이다 —
사내 문서와 직원 질문이 네트워크를 벗어나면 안 된다.

Windows CUDA 주의:
  ctranslate2 가 cublas64_12.dll 을 찾지 못해 CUDA 초기화에 실패한다.
  torch 가 같은 DLL 을 이미 번들하고 있으므로, import 전에 그 경로를
  등록하면 해결된다. _enable_cuda_dlls() 가 그 처리다.
"""
import os
import sys
import time
from dataclasses import dataclass


def _enable_cuda_dlls() -> bool:
    """torch 가 번들한 CUDA DLL 을 ctranslate2 가 찾을 수 있게 한다 (Windows)."""
    if os.name != "nt":
        return True
    try:
        import torch
        lib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(lib):
            os.add_dll_directory(lib)
            return True
    except Exception:
        pass
    return False


_enable_cuda_dlls()
from faster_whisper import WhisperModel  # noqa: E402  (DLL 등록 뒤에 import 해야 함)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import normalize_article_numbers  # noqa: E402


@dataclass
class STTResult:
    text: str              # 숫자 정규화까지 끝난 최종 텍스트
    text_raw: str          # 정규화 전 STT 원본 (CER 은 이걸로 잰다)
    audio_sec: float
    stt_ms: float
    normalize_ms: float
    avg_logprob: float     # 평균 log 확률 — 낮으면 인식이 불안하다
    no_speech_prob: float  # 무음 확률 — 높으면 재질문 대상

    @property
    def rtf(self) -> float:
        """실시간 배율. 처리 시간 / 음성 길이."""
        return (self.stt_ms / 1000) / self.audio_sec if self.audio_sec else 0.0


class STT:
    def __init__(self, size: str = "small", device: str = "cuda",
                 compute_type: str = "float16"):
        self.size, self.device = size, device
        self.model = WhisperModel(size, device=device, compute_type=compute_type)

    def warmup(self, wav_path: str) -> None:
        """첫 호출의 콜드 스타트를 서버 기동 시점으로 옮긴다."""
        self.transcribe(wav_path)

    def transcribe(self, wav_path: str) -> STTResult:
        t0 = time.perf_counter()
        segments, info = self.model.transcribe(wav_path, language="ko", beam_size=5)
        segs = list(segments)                      # 제너레이터라 여기서 실제 연산이 돈다
        stt_ms = (time.perf_counter() - t0) * 1000

        raw = "".join(s.text for s in segs).strip()

        t1 = time.perf_counter()
        text = normalize_article_numbers(raw)
        normalize_ms = (time.perf_counter() - t1) * 1000

        n = len(segs)
        return STTResult(
            text=text,
            text_raw=raw,
            audio_sec=float(info.duration),
            stt_ms=stt_ms,
            normalize_ms=normalize_ms,
            avg_logprob=sum(s.avg_logprob for s in segs) / n if n else -9.0,
            no_speech_prob=max((s.no_speech_prob for s in segs), default=1.0),
        )


if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    from question_sets import ALL
    D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")

    stt = STT(sys.argv[1] if len(sys.argv) > 1 else "small")
    print(f"모델 {stt.size} / {stt.device}\n")
    for qid, want in ALL[:5]:
        r = stt.transcribe(os.path.join(D, f"{qid}.wav"))
        print(f"  {qid}  {r.audio_sec:.1f}s  RTF {r.rtf:.3f}  logprob {r.avg_logprob:.2f}")
        print(f"     정답 {want}")
        print(f"     인식 {r.text_raw}")
        if r.text != r.text_raw:
            print(f"     정규화 {r.text}")
