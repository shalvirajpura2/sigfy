from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = DATA_DIR / "plan_documents"
INDEX_DIR = DATA_DIR / "index"

loaded = load_dotenv(BASE_DIR / ".env", override=True)


def _flag(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


class Settings:
    llm_provider: str = _flag("LLM_PROVIDER", "auto")
    anthropic_api_key: str = _flag("ANTHROPIC_API_KEY")
    anthropic_model: str = _flag("ANTHROPIC_MODEL", "claude-sonnet-5")
    openai_api_key: str = _flag("OPENAI_API_KEY")
    openai_model: str = _flag("OPENAI_MODEL", "gpt-4o-mini")
    openai_base_url: str = _flag("OPENAI_BASE_URL")
    max_tokens: int = int(_flag("LLM_MAX_TOKENS", "1600"))

    @property
    def provider(self) -> str:
        if self.llm_provider != "auto":
            return self.llm_provider
        if self.anthropic_api_key:
            return "anthropic"
        if self.openai_api_key:
            return "openai"
        return "none"

    @property
    def model(self) -> str:
        return self.openai_model if self.provider == "openai" else self.anthropic_model

    @property
    def has_llm(self) -> bool:
        return self.provider != "none"

    embeddings_provider: str = _flag("EMBEDDINGS_PROVIDER", "local")
    embeddings_model: str = _flag("EMBEDDINGS_MODEL", "BAAI/bge-small-en-v1.5")
    top_k: int = int(_flag("RETRIEVAL_TOP_K", "8"))

    # Evidence Validation Gate Thresholds
    val_dense_threshold: float = float(_flag("VAL_DENSE_THRESHOLD", "0.35"))
    val_bm25_minimal: float = float(_flag("VAL_BM25_MINIMAL", "1.0"))
    val_dense_very_high: float = float(_flag("VAL_DENSE_VERY_HIGH", "0.55"))
    val_bm25_strong: float = float(_flag("VAL_BM25_STRONG", "8.0"))

    # Metadata Fallback Thresholds
    fallback_dense_threshold: float = float(_flag("FALLBACK_DENSE_THRESHOLD", "0.35"))
    fallback_bm25_threshold: float = float(_flag("FALLBACK_BM25_THRESHOLD", "5.0"))

    chunk_chars: int = int(_flag("CHUNK_CHARS", "1100"))
    chunk_overlap: int = int(_flag("CHUNK_OVERLAP", "180"))

    api_key: str = _flag("API_KEY")
    allow_origins: str = _flag("ALLOW_ORIGINS", "*")

    @property
    def uses_local_embeddings(self) -> bool:
        return self.embeddings_provider == "local"


settings = Settings()
