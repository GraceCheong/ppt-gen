"""공유 상수 및 sys.path 초기화.

server/app/ 의 모든 모듈이 import 하는 첫 번째 모듈.
이 모듈이 로드되면 src/ 디렉터리가 sys.path에 추가되어
ppt_service, constants 등을 직접 import 할 수 있게 된다.
"""
from __future__ import annotations

import os
import sys

# server/app/config.py → server/app/ → server/ → project root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# .env 파일 로드 — env/.env 우선, 없으면 루트 .env 폴백
def _load_env(path: str) -> None:
    with open(path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

for _candidate in [
    os.path.join(ROOT_DIR, "env", ".env"),
    os.path.join(ROOT_DIR, ".env"),
]:
    if os.path.exists(_candidate):
        _load_env(_candidate)
        break

PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
TEMPLATE_SYNC_INTERVAL_SECONDS = 10 * 60
GENERATOR_VERSION = "direct-python-pptx-v4"
MAX_ERROR_REPORT_TEXT = 12000

# HTTPS 모드 — True이면 쿠키에 secure=True 적용 (Tauri sidecar는 HTTP이므로 기본 False)
HTTPS_MODE: bool = os.environ.get("PORR_HTTPS", "").lower() in ("1", "true", "yes")

# CORS 허용 오리진 — 쉼표로 구분. 기본값은 Vite dev server
_cors_env = os.environ.get("PORR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CORS_ORIGINS: list[str] = [o.strip() for o in _cors_env.split(",") if o.strip()]

# 파일 업로드 최대 크기 (bytes)
MAX_UPLOAD_BYTES: int = int(os.environ.get("PORR_MAX_UPLOAD_MB", "50")) * 1024 * 1024

# 악보 드라이브 super 계정 목록 (쉼표 구분)
_super_env = os.environ.get("PORR_SUPER_USERS", "")
SUPER_USERS: frozenset[str] = frozenset(
    u.strip() for u in _super_env.split(",") if u.strip()
)

# 데이터 루트 — 기본값은 프로젝트 루트/out. Google Drive 동기화 폴더 등으로 변경 가능.
DATA_DIR: str = os.environ.get("PORR_DATA_DIR", os.path.join(ROOT_DIR, "out"))

SHEET_DRIVE_DIR = os.path.join(DATA_DIR, "sheet_drive", "files")
SHEET_THUMB_DIR = os.path.join(DATA_DIR, "sheet_drive", "thumbs")

ALLOWED_SHEET_MIME_PREFIXES = ("image/",)
ALLOWED_SHEET_MIME_EXACT = ("application/pdf",)

# Google Drive 동기화 설정
GDRIVE_SYNC_ENABLED: bool = os.environ.get("GDRIVE_SYNC_ENABLED", "").lower() in ("1", "true", "yes")
GDRIVE_FOLDER_ID: str | None = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_SYNC_INTERVAL_SEC: int = int(os.environ.get("GDRIVE_SYNC_INTERVAL_SEC", "3600"))
GDRIVE_AUTH_MODE: str = os.environ.get("GDRIVE_AUTH_MODE", "oauth")
GDRIVE_OAUTH_CLIENT_JSON: str | None = os.environ.get("GDRIVE_OAUTH_CLIENT_JSON")
GDRIVE_OAUTH_TOKEN_PATH: str = os.environ.get(
    "GDRIVE_OAUTH_TOKEN_PATH",
    os.path.join(DATA_DIR, "sheet_drive", ".gdrive_oauth_token.json"),
)
