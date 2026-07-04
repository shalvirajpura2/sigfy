from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BASE_DIR  # noqa: E402
from app.retrieval import get_retriever  # noqa: E402

SAMPLES = json.loads(
    (BASE_DIR.parent / "eval" / "sample_emails.json").read_text(encoding="utf-8")
)


def _run(sample: dict) -> dict:
    r = get_retriever()
    chunks = r.search(f"{sample['subject']}\n{sample['body']}")
    docs = [c["document"] for c in chunks]
    joined = " ".join(c["text"].lower() for c in chunks)
    return {
        "top_doc": docs[0] if docs else None,
        "doc_in_topk": sample["expect_doc"] in docs,
        "terms_found": [t for t in sample["expect_terms"] if t.lower() in joined],
        "chunks": chunks,
    }


def test_all_samples_route_correctly():
    for s in SAMPLES:
        res = _run(s)
        assert res["doc_in_topk"], f"{s['id']}: expected {s['expect_doc']} in top-k, got {res['top_doc']}"
        assert res["terms_found"], f"{s['id']}: none of {s['expect_terms']} retrieved"


if __name__ == "__main__":
    for s in SAMPLES:
        res = _run(s)
        ok = res["doc_in_topk"] and res["terms_found"]
        print(f"[{'ok ' if ok else 'FAIL'}] {s['id']:20} top={res['top_doc']!r} "
              f"expect_doc_in_topk={res['doc_in_topk']} terms={res['terms_found']}")
