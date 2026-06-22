"""Job 상태 조회 및 결과 다운로드 엔드포인트."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from server.app.config import PPTX_MEDIA_TYPE
from server.app.jobs.job_models import JobStatus
from server.app.jobs.job_store import get_job, list_jobs

router = APIRouter()


@router.get("/api/jobs")
def list_all_jobs(limit: int = 100):
    return {"jobs": list_jobs(limit=limit)}


@router.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, detail=f"Job '{job_id}'를 찾을 수 없습니다.")
    return job.to_dict()


@router.get("/api/jobs/{job_id}/download", response_class=Response)
def download_job_output(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, detail=f"Job '{job_id}'를 찾을 수 없습니다.")
    if job.status != JobStatus.succeeded:
        raise HTTPException(
            400,
            detail=f"Job 상태가 '{job.status.value}'입니다. 완료(succeeded) 후 다운로드 가능합니다.",
        )
    if not job.output_path or not os.path.exists(job.output_path):
        raise HTTPException(404, detail="출력 파일을 찾을 수 없습니다.")

    with open(job.output_path, "rb") as f:
        content = f.read()

    ext = os.path.splitext(job.output_path)[1].lower()
    if ext == ".pptx":
        media_type = PPTX_MEDIA_TYPE
        filename = f"{job_id}.pptx"
    elif ext == ".png":
        media_type = "image/png"
        filename = f"{job_id}.png"
    else:
        media_type = "application/octet-stream"
        filename = os.path.basename(job.output_path)

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
