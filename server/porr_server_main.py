"""Tauri sidecar / 독립 실행용 서버 진입점.

PyInstaller로 번들할 때 이 파일이 main script가 된다.
"""
from __future__ import annotations

import argparse
import os
import sys


def _setup_paths() -> None:
    if getattr(sys, "frozen", False):
        # PyInstaller bundle: _MEIPASS 아래에 src/ 가 포함돼 있다
        bundle_dir = sys._MEIPASS  # type: ignore[attr-defined]
        src_dir = os.path.join(bundle_dir, "src")
    else:
        # 개발 환경: 프로젝트 루트 기준
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        src_dir = os.path.join(project_root, "src")

    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def main() -> None:
    _setup_paths()

    parser = argparse.ArgumentParser(description="PO,RR local server (sidecar)")
    parser.add_argument("--host", default="127.0.0.1", help="바인딩 호스트 (기본: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="포트 (기본: 8765)")
    parser.add_argument("--log-level", default="warning", help="uvicorn log level")
    args = parser.parse_args()

    import uvicorn
    from server.app.main import app  # noqa: F401 — side-effect: sys.path set up

    uvicorn.run(
        "server.app.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
