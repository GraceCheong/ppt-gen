"""생성 파일 경로 관리."""
from __future__ import annotations

import os

from server.app.config import DATA_DIR


def get_generated_pptx_path(job_id: str) -> str:
    path = os.path.join(DATA_DIR, "generated", "pptx")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f"{job_id}.pptx")


def get_songlist_card_path(job_id: str) -> str:
    path = os.path.join(DATA_DIR, "generated", "songlist")
    os.makedirs(path, exist_ok=True)
    return os.path.join(path, f"{job_id}.png")
