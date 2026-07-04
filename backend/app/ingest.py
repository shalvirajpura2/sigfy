from __future__ import annotations

import json
import re
import warnings

from pypdf import PdfReader

from .config import DOCS_DIR, INDEX_DIR, settings
from .documents import PLAN_DOCS


EFFECTIVE_RE = re.compile(
    r"effective\s+(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},?\s+(20\d{2})",
    re.IGNORECASE,
)
MONTH_YEAR_RE = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+\d{1,2},?\s+(20\d{2})\b",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    text = re.sub(r"(?<=\w)\ufffd(?=\w)", "'", text)
    text = re.sub(r"(?m)^\s*\ufffd\s*", "• ", text)
    text = text.replace("\ufffd", "-")
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_STOP_END = {
    "a", "an", "the", "and", "or", "of", "to", "for", "as", "in", "on", "with",
    "your", "you", "is", "are", "covered", "that", "this", "by", "at", "from",
}


def _looks_like_heading(line: str) -> bool:
    s = line.strip()
    if not (3 <= len(s) <= 70):
        return False
    if s.endswith((".", ",", ";", ":")):
        return False
    if s[0] in "•-*|(":
        return False
    if any(ch in s for ch in "$|@"):
        return False
    low = s.lower()
    if any(bad in low for bad in ("human energy", "http", "hr2.chevron", "(continued")):
        return False
    if re.search(r"\d{3}[-.\s]\d{3,4}", s):
        return False
    words = s.split()
    if not (1 <= len(words) <= 9):
        return False
    if words[-1].lower() in _STOP_END:
        return False
    if len(words[0]) == 1 and words[0].islower():
        return False
    alpha = sum(c.isalpha() for c in s)
    return alpha >= len(s) * 0.6


def _normalize_heading(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip()).strip(" -•")


def _effective_date(text: str) -> str:
    m = EFFECTIVE_RE.search(text)
    if m:
        return f"{m.group(1).title()} {m.group(2)}"
    return ""


def build_chunks() -> list[dict]:
    """walk each document line by line, carrying the nearest preceding heading and
    the current effective date, and emit ~chunk_chars windows tagged with both plus
    the page where the chunk starts. sections/dates flow across page boundaries."""
    size = settings.chunk_chars
    overlap = settings.chunk_overlap
    chunks: list[dict] = []

    for doc in PLAN_DOCS:
        path = DOCS_DIR / doc.filename
        if not path.exists():
            raise FileNotFoundError(f"missing plan document: {path}")
        reader = PdfReader(str(path))

        current_section = ""
        current_eff = ""
        buffer = ""
        buf_page: int | None = None
        buf_section = ""

        def emit(text: str) -> None:
            if len(text) < 40:
                return
            chunks.append({
                "id": f"{doc.id}:{len(chunks)}",
                "doc_id": doc.id,
                "document": doc.title,
                "page": buf_page,
                "section": buf_section,
                "effective_date": _effective_date(text) or current_eff,
                "text": text,
            })

        for page_num, page in enumerate(reader.pages, start=1):
            raw = _clean(page.extract_text() or "")
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                eff = _effective_date(line)
                if eff:
                    current_eff = eff
                if _looks_like_heading(line):
                    current_section = _normalize_heading(line)
                if not buffer:
                    buf_page, buf_section = page_num, current_section
                if len(buffer) + len(line) + 1 <= size:
                    buffer = f"{buffer} {line}".strip()
                else:
                    emit(buffer)
                    tail = buffer[-overlap:] if overlap else ""
                    buffer = f"{tail} {line}".strip()
                    buf_page, buf_section = page_num, current_section
        emit(buffer)
    return chunks


def write_index() -> dict:
    from .embeddings import embed_documents

    chunks = build_chunks()
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8"
    )

    meta = {"count": len(chunks), "embeddings": settings.embeddings_provider}
    if settings.uses_local_embeddings:
        import numpy as np

        vectors = embed_documents([c["text"] for c in chunks])
        np.save(INDEX_DIR / "embeddings.npy", vectors)
        meta["embeddings_model"] = settings.embeddings_model
        meta["dim"] = int(vectors.shape[1])

    (INDEX_DIR / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    print(json.dumps(write_index(), indent=2))
