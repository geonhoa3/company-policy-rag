# src/audit.py — 모든 Q&A를 기록하는 감사 로그 (책임 추적용)
import json, os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
LOG_FILE = os.path.join(LOG_DIR, "qa_log.jsonl")

def log_turn(question: str, answer: str, hits: list, extra_fact: str = "", feedback=None):
    """질문·답변·근거 조항·유사도를 한 줄(JSON)로 append. 사후 검증 가능."""
    os.makedirs(LOG_DIR, exist_ok=True)
    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "question": question,
        "answer": answer,
        "top_article": hits[0][0]["article_no"] if hits else None,
        "top_score": round(float(hits[0][1]), 3) if hits else None,
        "cited": [c["article_no"] for c, _ in hits],
        "computed_fact": extra_fact,   # 코드가 계산한 값(연차 등)이 있으면 기록
        "feedback": feedback,          # 👎 신고 시 표시
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
