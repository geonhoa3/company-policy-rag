# src/embedder.py
from sentence_transformers import SentenceTransformer
import numpy as np

MODEL_NAME = "BAAI/bge-m3"        # 나중에 여기만 바꾸면 모델 교체
_model = None                      # 모델은 무겁다 → 한 번만 로드해 재사용

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def embed_texts(texts: list[str]) -> np.ndarray:
    model = get_model()
    # TODO) texts 를 인코딩해서 정규화된 벡터 배열로 반환
    #  힌트: model.encode(texts, normalize_embeddings=True)
    return model.encode(texts, normalize_embeddings=True)