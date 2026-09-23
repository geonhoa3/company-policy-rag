# src/store.py
import json, os, re
import numpy as np
from src.embedder import embed_texts

# "제27조가 뭐야?" 같은 질문은 의미를 비교할 게 거의 없어서 벡터 검색에 불리하다.
# (실측: 내용 질문은 0.65~0.73이 나오는데 번호 질문은 0.43~0.50까지 떨어져
#  정답을 1위로 찾고도 신뢰도 경고가 뜨는 역전이 생긴다.)
# 번호 질문은 '검색'이 아니라 '조회' 문제이므로 정규식으로 잡아 직접 꺼낸다.
ARTICLE_Q_RE = re.compile(r"제\s*(\d+)\s*조")
EXACT_SCORE = 1.0          # 번호로 직접 찾은 조항의 점수 (유사도가 아니라 '정확 일치')

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

def lookup_by_article_no(query: str, chunks: list[dict]):
    """질문에 '제N조'가 있으면 그 조항을 직접 꺼낸다. 없으면 None.

    항 단위로 쪼개진 조는 조각을 전부, part 순서대로 돌려준다.
    """
    m = ARTICLE_Q_RE.search(query)
    if not m:
        return None
    no = int(m.group(1))
    hits = [c for c in chunks if c["article_no"] == no]
    if not hits:
        return None                       # 없는 조 번호 → 벡터 검색에 맡김
    hits.sort(key=lambda c: c.get("part", 1))
    return [(c, EXACT_SCORE) for c in hits]


def search(query: str, chunks: list[dict], vecs: np.ndarray, k: int = 3):
    exact = lookup_by_article_no(query, chunks)
    if exact:
        return exact                      # 번호 조회는 k에 묶이지 않는다 (조각 전부 반환)

    q = embed_texts([query])[0]           # 질문도 같은 임베더로 (슬롯3 금지선)
    sims = vecs @ q                        # 정규화돼서 내적 = 코사인 유사도
    # TODO) sims 가 큰 순서로 상위 k개의 인덱스를 뽑아라
    #  힌트: np.argsort(sims) 는 '작은→큰' 순. 뒤집고([::-1]) 앞 k개([:k])
    top_idx = np.argsort(sims)[::-1][:k]
    return [(chunks[i], float(sims[i])) for i in top_idx]