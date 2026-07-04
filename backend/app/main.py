from __future__ import annotations

import logging

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from . import tasks
from .generate import generate_draft
from .models import DraftRequest, DraftResponse, BatchDraftRequest, BatchDraftResponse
from .retrieval import get_retriever

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("benefits")

import time
import hashlib

app = FastAPI(title="sigfy benefits email assistant", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.allow_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _authorize(x_api_key: str | None) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing api key")


@app.get("/health")
def health() -> dict:
    try:
        r = get_retriever()
        return {
            "status": "ok",
            "chunks": len(r.chunks),
            "dense_retrieval": r.dense_enabled,
            "provider": settings.provider,
            "model": settings.model,
            "generation": "live" if settings.has_llm else "dry-run",
        }
    except Exception as exc:
        return {"status": "degraded", "detail": str(exc)}


@app.post("/draft", response_model=DraftResponse)
def draft(req: DraftRequest, x_api_key: str | None = Header(default=None)) -> DraftResponse:
    _authorize(x_api_key)
    # Relevance filter: only process benefits‑related emails if ALLOWED_KEYWORDS is set
    if settings.allowed_keywords:
        combined_text = f"{req.subject} {req.body}".lower()
        if not any(kw.lower() in combined_text for kw in settings.allowed_keywords):
            log.info("[Filter] Email does not match allowed keywords – skipping draft generation")
            return DraftResponse(
                found=False,
                confidence="low",
                draft="The email does not appear to be benefits‑related, so no draft was generated.",
                citations=[],
                notes="Filtered out by allowed_keywords configuration.",
                model="none",
                retrieved=[],
            )

        raise HTTPException(status_code=422, detail="email body is empty")

    start_time = time.time()
    query = f"{req.subject}\n{req.body}".strip()
    q_hash = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]

    ret_start = time.time()
    chunks = get_retriever().search(query)
    ret_ms = round((time.time() - ret_start) * 1000, 2)

    from .retrieval import validate_evidence
    top_chunk = chunks[0] if chunks else None
    gate_passed = validate_evidence(top_chunk)

    log.info(
        "[RAG Trace] req_id=%s | retrieved=%d chunks (time: %s ms) | top_dense=%s | top_bm25=%s | gate=%s",
        q_hash,
        len(chunks),
        ret_ms,
        round(top_chunk.get("dense_score", 0.0), 4) if top_chunk else 0.0,
        round(top_chunk.get("bm25_score", 0.0), 4) if top_chunk else 0.0,
        "PASS" if gate_passed else "REJECT"
    )

    gen_start = time.time()
    resp = generate_draft(req.subject, req.sender, req.receiver, req.body, chunks, debug=req.debug)
    gen_ms = round((time.time() - gen_start) * 1000, 2)

    total_ms = round((time.time() - start_time) * 1000, 2)
    log.info(
        "[RAG Trace] req_id=%s | LLM_invoked=%s | gen_time=%s ms | total_time=%s ms",
        q_hash,
        "YES" if (gate_passed and settings.has_llm) else "NO (bypass/dry-run)",
        gen_ms,
        total_ms
    )

    return resp


@app.post("/batch_draft", response_model=BatchDraftResponse)
def batch_draft(batch_req: BatchDraftRequest, x_api_key: str | None = Header(default=None)) -> BatchDraftResponse:
    # Authorize once for the batch request
    _authorize(x_api_key)
    responses: list[DraftResponse] = []
    for req in batch_req.requests:
        # Reuse the existing draft logic per request
        resp = draft(req, x_api_key)
        responses.append(resp)
    return BatchDraftResponse(responses=responses)
# ---------------------------------------------------------------------------
# Asynchronous batch processing (fire‑and‑forget, task‑id polling)
# ---------------------------------------------------------------------------

@app.post("/batch_draft_async")
def batch_draft_async(batch_req: BatchDraftRequest, x_api_key: str | None = Header(default=None)):
    """Enqueue a batch draft job and immediately return a task identifier."""
    _authorize(x_api_key)
    task_id = tasks.create_task(batch_req, x_api_key)
    return {"task_id": task_id}

@app.get("/task_status/{task_id}")
def task_status(task_id: str):
    """Poll the status of an asynchronous batch job. Returns the final result when finished."""
    t = tasks.get_task(task_id)
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    result: dict = {"status": t.status}
    if t.status == tasks.TaskStatus.FINISHED:
        result["responses"] = t.responses
    if t.status == tasks.TaskStatus.FAILED:
        result["error"] = t.error_msg
    return result

@app.post("/task_cancel/{task_id}")
def task_cancel(task_id: str):
    """Request cancellation of a running or pending async batch job."""
    if tasks.cancel_task(task_id):
        return {"status": "CANCELLED"}
    else:
        raise HTTPException(status_code=400, detail="Cannot cancel – task not pending or running")
