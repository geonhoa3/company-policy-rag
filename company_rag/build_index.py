# build_index.py
from src.loader import load_docx
from src.chunker import chunk_by_article, split_long_articles, MAX_CHARS
from src.embedder import embed_texts
from src.store import save_index

DOCX = "data/사규_취업규칙_샘플.docx"
INDEX_DIR = "index"

articles = chunk_by_article(load_docx(DOCX))
chunks = split_long_articles(articles)

# 길이 가드가 실제로 걸렸는지 눈에 보이게 — 조용히 잘리는 게 제일 위험하다
split_count = sum(1 for c in chunks if c["n_parts"] > 1)
longest = max(len(c["text"]) for c in chunks)
print(f"조 {len(articles)}개 → 청크 {len(chunks)}개 "
      f"(항 분할된 조: {split_count}개, 최장 청크 {longest}자 / 상한 {MAX_CHARS}자)")

# 항 하나가 단독으로 상한을 넘으면 더 못 쪼갠다 → 반드시 알려야 함
for c in chunks:
    if len(c["text"]) > MAX_CHARS:
        print(f"  ⚠️ 제{c['article_no']}조 ({c['article_title']}) {c['part']}/{c['n_parts']} "
              f"— {len(c['text'])}자: 항 하나가 상한을 넘어 더 분할할 수 없음")

vecs = embed_texts([c["text"] for c in chunks])
save_index(chunks, vecs, INDEX_DIR)
print(f"✅ 색인 완료: {len(chunks)}개 청크 → {INDEX_DIR}/")
