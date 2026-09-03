# build_index.py
from src.loader import load_docx
from src.chunker import chunk_by_article
from src.embedder import embed_texts
from src.store import save_index

DOCX = "data/사규_취업규칙_샘플.docx"
INDEX_DIR = "index"

chunks = chunk_by_article(load_docx(DOCX))
vecs = embed_texts([c["text"] for c in chunks])
save_index(chunks, vecs, INDEX_DIR)
print(f"✅ 색인 완료: {len(chunks)}개 조항 → {INDEX_DIR}/")