"""server/app/jobs/ 단위 테스트."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import re
from server.app.jobs.job_models import ExportJob, JobStatus
from server.app.jobs.job_store import (
    create_job,
    get_job,
    list_jobs,
    new_job_id,
    update_job,
)


# ── new_job_id ────────────────────────────────────────────────────────────────

def test_new_job_id_format():
    jid = new_job_id()
    assert re.match(r"^job_\d{8}_\d{6}_[0-9a-f]{8}$", jid), f"unexpected format: {jid}"


def test_new_job_id_unique():
    ids = {new_job_id() for _ in range(50)}
    assert len(ids) == 50


# ── create_job ────────────────────────────────────────────────────────────────

def test_create_pptx_job():
    job = create_job("pptx")
    assert job.type == "pptx"
    assert job.status == JobStatus.queued
    assert job.progress == 0
    assert job.message is None
    assert job.output_path is None
    assert job.download_url is None
    assert job.error is None


def test_create_songlist_job():
    job = create_job("songlist_card")
    assert job.type == "songlist_card"
    assert job.status == JobStatus.queued


def test_created_job_retrievable():
    job = create_job("pptx")
    fetched = get_job(job.id)
    assert fetched is not None
    assert fetched.id == job.id


# ── get_job ───────────────────────────────────────────────────────────────────

def test_get_nonexistent_job_returns_none():
    assert get_job("does_not_exist_abc123") is None


# ── update_job ────────────────────────────────────────────────────────────────

def test_update_status_to_running():
    job = create_job("pptx")
    update_job(job.id, status=JobStatus.running, progress=20, message="생성 중")
    fetched = get_job(job.id)
    assert fetched.status == JobStatus.running
    assert fetched.progress == 20
    assert fetched.message == "생성 중"


def test_update_status_to_succeeded():
    job = create_job("pptx")
    update_job(
        job.id,
        status=JobStatus.succeeded,
        progress=100,
        output_path="/tmp/test.pptx",
        download_url=f"/api/jobs/{job.id}/download",
    )
    fetched = get_job(job.id)
    assert fetched.status == JobStatus.succeeded
    assert fetched.progress == 100
    assert fetched.output_path == "/tmp/test.pptx"
    assert fetched.download_url == f"/api/jobs/{job.id}/download"


def test_update_status_to_failed():
    job = create_job("pptx")
    update_job(job.id, status=JobStatus.failed, error="테스트 오류")
    fetched = get_job(job.id)
    assert fetched.status == JobStatus.failed
    assert fetched.error == "테스트 오류"


def test_update_nonexistent_job_is_noop():
    update_job("nonexistent_xyz", status=JobStatus.running)  # should not raise


def test_updated_at_changes():
    job = create_job("pptx")
    before = job.updated_at
    update_job(job.id, progress=50)
    fetched = get_job(job.id)
    assert fetched.updated_at >= before


# ── to_dict ───────────────────────────────────────────────────────────────────

def test_to_dict_does_not_expose_output_path():
    job = create_job("pptx")
    update_job(job.id, output_path="/secret/path/output.pptx", download_url="/api/jobs/x/download")
    d = get_job(job.id).to_dict()
    assert "output_path" not in d
    assert "download_url" in d


def test_to_dict_status_is_string():
    job = create_job("pptx")
    d = job.to_dict()
    assert isinstance(d["status"], str)
    assert d["status"] == "queued"


def test_to_dict_datetimes_are_isoformat():
    job = create_job("pptx")
    d = job.to_dict()
    assert "T" in d["created_at"]
    assert "T" in d["updated_at"]


# ── list_jobs ─────────────────────────────────────────────────────────────────

def test_list_jobs_returns_dicts():
    create_job("pptx")
    jobs = list_jobs()
    assert isinstance(jobs, list)
    assert all(isinstance(j, dict) for j in jobs)


def test_list_jobs_limit():
    for _ in range(5):
        create_job("pptx")
    jobs = list_jobs(limit=3)
    assert len(jobs) <= 3
