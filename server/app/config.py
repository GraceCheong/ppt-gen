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

# .env 파일 로드 (git에 커밋되지 않은 비밀 값 포함)
_env_file = os.path.join(ROOT_DIR, ".env")
if os.path.exists(_env_file):
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

PPTX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
TEMPLATE_SYNC_INTERVAL_SECONDS = 10 * 60
GENERATOR_VERSION = "direct-python-pptx-v4"
MAX_ERROR_REPORT_TEXT = 12000
