from __future__ import annotations

import numpy as np

from .config import settings

_model = None


def _load():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embeddings_model)
    return _model


def embed_documents(texts: list[str]) -> np.ndarray:
    model = _load()
    return model.encode(
        texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True
    ).astype("float32")


def embed_query(text: str) -> np.ndarray:
    model = _load()
    prefix = "Represent this sentence for searching relevant passages: "
    return model.encode([prefix + text], normalize_embeddings=True).astype("float32")[0]
