"""음성 평가셋 녹음 도구 (실행: python voice/record.py)

질문을 화면에 띄우고 Enter 로 녹음을 시작/종료해 16kHz 모노 wav 로 저장한다.
파일명이 질문 ID 라 68개를 녹음해도 라벨이 섞이지 않고, 마이크 조건도 일정하다.
ffmpeg 없이 바로 평가에 쓸 수 있는 포맷으로 저장된다.

  python voice/record.py                # 아직 녹음 안 된 것만 이어서
  python voice/record.py --set number   # 특정 세트만
  python voice/record.py --redo num13   # 특정 질문 다시
  python voice/record.py --list         # 진행 상황만 확인
"""
import argparse
import os
import queue
import sys
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from question_sets import ALL, SETS

SR = 16000                       # faster-whisper 가 기대하는 샘플레이트
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recordings")


def record_until_enter() -> np.ndarray:
    """Enter 를 누를 때까지 마이크 입력을 모은다."""
    frames: "queue.Queue[np.ndarray]" = queue.Queue()
    stop = threading.Event()

    def cb(indata, _frames, _time, status):
        if status:
            print(f"  (입력 경고: {status})", file=sys.stderr)
        frames.put(indata.copy())

    with sd.InputStream(samplerate=SR, channels=1, dtype="float32", callback=cb):
        threading.Thread(target=lambda: (input(), stop.set()), daemon=True).start()
        while not stop.is_set():
            sd.sleep(50)

    chunks = []
    while not frames.empty():
        chunks.append(frames.get())
    return np.concatenate(chunks).ravel() if chunks else np.zeros(0, dtype="float32")


def path_for(qid: str) -> str:
    return os.path.join(OUT_DIR, f"{qid}.wav")


def review(audio: np.ndarray) -> str:
    """녹음 직후 상태를 보여주고 다시 할지 묻는다."""
    dur = len(audio) / SR
    peak = float(np.abs(audio).max()) if audio.size else 0.0
    warn = ""
    if dur < 0.8:
        warn = "  ⚠️ 너무 짧습니다"
    elif peak < 0.02:
        warn = "  ⚠️ 소리가 거의 없습니다 (마이크 확인)"
    elif peak > 0.99:
        warn = "  ⚠️ 음량이 큽니다 (클리핑 가능)"
    print(f"  길이 {dur:.1f}초 / 최대음량 {peak:.2f}{warn}")
    return input("  [Enter] 저장  |  r: 다시  |  s: 건너뛰기  |  q: 종료 > ").strip().lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="setname", choices=sorted(SETS), help="특정 세트만")
    ap.add_argument("--redo", help="특정 질문 ID 다시 녹음")
    ap.add_argument("--list", action="store_true", help="진행 상황만 출력")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)

    if args.list:
        for name, items in SETS.items():
            done = sum(1 for qid, _ in items if os.path.exists(path_for(qid)))
            print(f"  {name:<8} {done:>3}/{len(items)}")
        missing = [qid for qid, _ in ALL if not os.path.exists(path_for(qid))]
        print(f"\n남은 질문 {len(missing)}개" + (f": {', '.join(missing[:12])}" if missing else ""))
        return

    if args.redo:
        todo = [(q, t) for q, t in ALL if q == args.redo]
        if not todo:
            print(f"❌ 그런 질문 ID 가 없습니다: {args.redo}")
            return
    else:
        pool = SETS[args.setname] if args.setname else ALL
        todo = [(q, t) for q, t in pool if not os.path.exists(path_for(q))]

    if not todo:
        print("✅ 녹음할 게 없습니다. --list 로 확인하세요.")
        return

    print(f"마이크: {sd.query_devices(kind='input')['name']}")
    print(f"{SR}Hz 모노 / 저장 위치 {OUT_DIR}")
    print(f"녹음할 질문 {len(todo)}개\n")
    # 읽는 방식이 중간에 바뀌면 번호 인식률이 STT 성능이 아니라 발화 차이를 재게 된다
    print("  읽는 방법: '제27조' → \"제이십칠조\" 처럼 자연스럽게. 숫자를 끊어 읽지 않습니다.")
    print("  68개 내내 같은 방식, 마이크와 거리도 일정하게 유지하세요.\n")

    for n, (qid, text) in enumerate(todo, 1):
        while True:
            print(f"[{n}/{len(todo)}] {qid}")
            print(f"  \"{text}\"")
            cmd = input("  [Enter] 녹음 시작  |  s: 건너뛰기  |  q: 종료 > ").strip().lower()
            if cmd == "q":
                print("종료합니다.")
                return
            if cmd == "s":
                break

            print("  ● 녹음 중... 다 읽으면 [Enter]")
            audio = record_until_enter()

            action = review(audio)
            if action == "q":
                print("종료합니다.")
                return
            if action == "r":
                print()
                continue
            if action == "s":
                break

            sf.write(path_for(qid), audio, SR)
            print(f"  저장: {qid}.wav\n")
            break

    done = sum(1 for qid, _ in ALL if os.path.exists(path_for(qid)))
    print(f"진행 상황: {done}/{len(ALL)}")


if __name__ == "__main__":
    main()
