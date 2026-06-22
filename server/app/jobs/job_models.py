from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class ExportJob:
    id: str
    type: Literal["pptx", "songlist_card"]
    status: JobStatus
    progress: int = 0
    message: str | None = None
    output_path: str | None = None
    download_url: str | None = None
    error: str | None = None
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "download_url": self.download_url,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
