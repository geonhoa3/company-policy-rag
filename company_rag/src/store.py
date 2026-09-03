# src/store.py
import json, os
import numpy as np
from src.embedder import embed_texts

def save_index(chunks, vecs, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "vectors.npy"), vecs)
    with open(os.path.join(out_dir, "chunks.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

def load_index(out_dir):
    vecs = np.load(os.path.join(out_dir, "vectors.npy"))
    with open(os.path.join(out_dir, "chunks.json"), encoding="utf-8") as f:
        chunks = json.load(f)
    return chunks, vecs

def search(query: str, chunks: list[dict], vecs: np.ndarray, k: int = 3):
    q = embed_texts([query])[0]           # 질문도 같은 임베더로 (슬롯3 금지선)
    sims = vecs @ q                        # 정규화돼서 내적 = 코사인 유사도
    # TODO) sims 가 큰 순서로 상위 k개의 인덱스를 뽑아라
    #  힌트: np.argsort(sims) 는 '작은→큰' 순. 뒤집고([::-1]) 앞 k개([:k])
    top_idx = np.argsort(sims)[::-1][:k]
    return [(chunks[i], float(sims[i])) for i in top_idx]