from __future__ import annotations

import json
import re

import numpy as np
from rank_bm25 import BM25Okapi

from .config import INDEX_DIR, settings

_TOKEN_RE = re.compile(r"[a-z0-9$]+")
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "as", "in", "on", "with",
    "your", "you", "is", "are", "that", "this", "by", "at", "from", "what", "how",
    "why", "where", "who", "which", "it", "its", "i", "me", "my", "we", "us", "our"
}


def _tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class Retriever:
    """hybrid retrieval: BM25 (lexical) fused with dense cosine (semantic).

    lexical catches exact terms — dollar limits, plan names, "orthodontic
    lifetime maximum". semantic catches paraphrases — "braces" -> orthodontia,
    "travel costs" -> lodging/transportation. reciprocal-rank fusion needs no
    score calibration between the two.
    """

    def __init__(self) -> None:
        chunks_path = INDEX_DIR / "chunks.json"
        if not chunks_path.exists():
            raise FileNotFoundError(
                "index not built. run: python -m app.ingest (or scripts/build_index.py)"
            )
        self.chunks: list[dict] = json.loads(chunks_path.read_text(encoding="utf-8"))
        self.bm25 = BM25Okapi([_tokenize(c["text"]) for c in self.chunks])

        self.embeddings: np.ndarray | None = None
        emb_path = INDEX_DIR / "embeddings.npy"
        if settings.uses_local_embeddings and emb_path.exists():
            self.embeddings = np.load(emb_path)

    @property
    def dense_enabled(self) -> bool:
        return self.embeddings is not None

    def _rrf(self, ranking: list[int], table: dict[int, float], weight: float, k: int = 20):
        for rank, idx in enumerate(ranking):
            table[idx] = table.get(idx, 0.0) + weight / (k + rank + 1)

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        top_k = top_k or settings.top_k
        pool = max(top_k * 4, 30)

        # Get matching document IDs from keywords
        detected_docs = set()
        q_lower = query.lower()
        from .documents import PLAN_DOCS
        for doc in PLAN_DOCS:
            if any(k in q_lower for k in doc.keywords):
                detected_docs.add(doc.id)

        def do_search(doc_ids: set[str] | None) -> list[dict]:
            if doc_ids:
                indices = [i for i, c in enumerate(self.chunks) if c["doc_id"] in doc_ids]
            else:
                indices = list(range(len(self.chunks)))
            
            if not indices:
                return []

            bm25_scores = self.bm25.get_scores(_tokenize(query))
            sub_bm25_scores = bm25_scores[indices]
            sub_bm25_rank = np.argsort(sub_bm25_scores)[::-1][:pool].tolist()
            bm25_rank = [indices[idx] for idx in sub_bm25_rank]

            fused: dict[int, float] = {}
            self._rrf(bm25_rank, fused, weight=1.5)

            cos = None
            if self.dense_enabled:
                from .embeddings import embed_query
                q = embed_query(query)
                cos = self.embeddings @ q
                sub_cos = cos[indices]
                sub_dense_rank = np.argsort(sub_cos)[::-1][:pool].tolist()
                dense_rank = [indices[idx] for idx in sub_dense_rank]
                self._rrf(dense_rank, fused, weight=1.0)

            ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
            results = []
            for idx, score in ordered:
                chunk = dict(self.chunks[idx])
                chunk["score"] = round(float(score), 5)
                chunk["bm25_score"] = float(bm25_scores[idx])
                chunk["dense_score"] = float(cos[idx]) if cos is not None else 0.0
                results.append(chunk)
            return results

        if detected_docs:
            results = do_search(detected_docs)
            has_strong_evidence = False
            if results:
                top_chunk = results[0]
                if (top_chunk["dense_score"] >= settings.fallback_dense_threshold or
                        top_chunk["bm25_score"] >= settings.fallback_bm25_threshold):
                    has_strong_evidence = True
            if not has_strong_evidence:
                results = do_search(None)
        else:
            results = do_search(None)

        return results


def validate_evidence(top_chunk: dict | None) -> bool:
    if not top_chunk:
        return False
    dense = top_chunk.get("dense_score", 0.0)
    bm25 = top_chunk.get("bm25_score", 0.0)
    if dense >= settings.val_dense_threshold and bm25 >= settings.val_bm25_minimal:
        return True
    if bm25 >= settings.val_bm25_strong:
        return True
    if dense >= settings.val_dense_very_high:
        return True
    return False


_retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
    return _retriever
