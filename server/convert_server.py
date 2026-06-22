"""
PPT 생성/변환 서버 — 호환성 진입점 (thin shim)

실행 방법:
    uvicorn server.convert_server:app --host 0.0.0.0 --port 8010

PNG 변환에는 Windows + Microsoft PowerPoint 또는 LibreOffice가 필요합니다.
실제 구현은 server/app/ 패키지에 있습니다.
"""
from server.app.main import app  # noqa: F401

__all__ = ["app"]
