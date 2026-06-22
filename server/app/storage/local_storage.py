"""생성 파일 경로 관리."""
from __future__ import annotations

import os

from server.app.config import ROOT_DIR


def get_generated_pptx_path(job_id: str) -> str:
    path = os.path.join(ROOT_DIR, "out", "generated", "pptx")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f"{job_id}.pptx")


def get_songlist_card_path(job_id: str) -> str:
    path = os.path.join(ROOT_DIR, "out", "generated", "songlist")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f"{job_id}.png")
