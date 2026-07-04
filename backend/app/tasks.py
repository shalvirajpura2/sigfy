from __future__ import annotations
"""Simple in‑memory background task manager for batch draft processing."""

import asyncio
import uuid
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from .models import BatchDraftRequest, BatchDraftResponse, DraftResponse
from .main import draft, _authorize

log = logging.getLogger("benefits.tasks")


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TaskResult:
    status: TaskStatus = TaskStatus.PENDING
    responses: Optional[BatchDraftResponse] = None
    error_msg: Optional[str] = None
    cancel_requested: bool = False

# In‑memory registry
tasks: dict[str, TaskResult] = {}


async def _process_batch(task_id: str, batch_req: BatchDraftRequest, api_key: str | None) -> None:
    """Core coroutine that runs the batch synchronously in a thread pool."""
    t = tasks[task_id]
    t.status = TaskStatus.RUNNING
    log.info("[AsyncTask %s] started – %d requests", task_id, len(batch_req.requests))

    responses: List[DraftResponse] = []
    try:
        for i, req in enumerate(batch_req.requests, start=1):
            if t.cancel_requested:
                t.status = TaskStatus.CANCELLED
                log.info("[AsyncTask %s] cancelled after %d/%d", task_id, i - 1, len(batch_req.requests))
                return
            # Run the existing draft endpoint in a thread pool (it is sync)
            resp: DraftResponse = await asyncio.to_thread(draft, req, api_key)
            responses.append(resp)
    except Exception as exc:  # pragma: no‑cover – safety net
        t.status = TaskStatus.FAILED
        t.error_msg = str(exc)
        log.exception("[AsyncTask %s] failed", task_id)
        return

    t.responses = BatchDraftResponse(responses=responses)
    t.status = TaskStatus.FINISHED
    log.info("[AsyncTask %s] finished", task_id)


def create_task(batch_req: BatchDraftRequest, api_key: str | None) -> str:
    """Create a task, store placeholder, schedule coroutine, return its UUID."""
    task_id = str(uuid.uuid4())
    tasks[task_id] = TaskResult()
    asyncio.create_task(_process_batch(task_id, batch_req, api_key))
    return task_id


def get_task(task_id: str) -> Optional[TaskResult]:
    return tasks.get(task_id)


def cancel_task(task_id: str) -> bool:
    t = tasks.get(task_id)
    if t and t.status in {TaskStatus.PENDING, TaskStatus.RUNNING}:
        t.cancel_requested = True
        return True
    return False
