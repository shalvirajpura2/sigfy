from __future__ import annotations

from pydantic import BaseModel, Field


class DraftRequest(BaseModel):
    subject: str = ""
    sender: str = ""
    receiver: str = ""
    body: str
    debug: bool = False


class Citation(BaseModel):
    document: str
    section: str = ""
    page: int | None = None
    quote: str = ""
    chunk_id: str = ""
    effective_date: str = ""
    retrieval_score: float = 0.0


class RetrievedChunk(BaseModel):
    document: str
    section: str = ""
    page: int | None = None
    effective_date: str = ""
    score: float = 0.0
    text: str = ""


class DraftResponse(BaseModel):
    found: bool = Field(description="whether the plan documents clearly answer the question")
    confidence: str = "medium"  # high | medium | low
    draft: str = ""
    citations: list[Citation] = []
    notes: str = ""
    model: str = ""
    retrieved: list[RetrievedChunk] = []

# Batch request/response models
class BatchDraftRequest(BaseModel):
    requests: list[DraftRequest] = Field(..., description="List of email draft requests")

class BatchDraftResponse(BaseModel):
    responses: list[DraftResponse] = Field(..., description="Corresponding draft responses for each request")
