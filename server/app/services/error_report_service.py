"""오류 리포트 저장 서비스."""
from __future__ import annotations

import datetime
import json
import os

from fastapi import Request

from server.app.config import ROOT_DIR, MAX_ERROR_REPORT_TEXT


def error_report_dir() -> str:
    path = os.path.join(ROOT_DIR, "out", "error_reports")
    os.makedirs(path, exist_ok=True)
    return path


def trim_report_text(value, limit: int = MAX_ERROR_REPORT_TEXT) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[trimmed]"


def sanitize_report(data: dict, request: Request) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    client_host = request.client.host if request.client else ""
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}

    return {
        "received_at": now.isoformat(),
        "client_host": client_host,
        "reported_at": trim_report_text(data.get("reported_at"), 200),
        "context": trim_report_text(data.get("context"), 300),
        "message": trim_report_text(data.get("message"), 1000),
        "traceback": trim_report_text(data.get("traceback")),
        "extra": extra,
        "log_tail": data.get("log_tail") if isinstance(data.get("log_tail"), list) else [],
        "runtime": data.get("runtime") if isinstance(data.get("runtime"), dict) else {},
    }


def save_error_report(report: dict) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    file_path = os.path.join(error_report_dir(), f"{now:%Y-%m-%d}.jsonl")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")
    return file_path
