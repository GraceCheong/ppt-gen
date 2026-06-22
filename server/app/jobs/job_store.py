"""메모리 기반 Job 저장소 (1차 구현)."""
from __future__ import annotations

import datetime
import threading
import uuid

from server.app.jobs.job_models import ExportJob, JobStatus

_store: dict[str, ExportJob] = {}
_lock = threading.Lock()


def new_job_id() -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    return f"job_{ts}_{uid}"


def create_job(job_type: str) -> ExportJob:
    job_id = new_job_id()
    now = datetime.datetime.now(datetime.timezone.utc)
    job = ExportJob(
        id=job_id,
        type=job_type,  # type: ignore[arg-type]
        status=JobStatus.queued,
        created_at=now,
        updated_at=now,
    )
    with _lock:
        _store[job_id] = job
    return job


def get_job(job_id: str) -> ExportJob | None:
    with _lock:
        return _store.get(job_id)


def update_job(job_id: str, **kwargs) -> None:
    with _lock:
        job = _store.get(job_id)
        if job is None:
            return
        for key, value in kwargs.items():
            setattr(job, key, value)
        job.updated_at = datetime.datetime.now(datetime.timezone.utc)


def list_jobs(limit: int = 100) -> list[dict]:
    with _lock:
        jobs = sorted(_store.values(), key=lambda j: j.created_at, reverse=True)
    return [j.to_dict() for j in jobs[:limit]]
