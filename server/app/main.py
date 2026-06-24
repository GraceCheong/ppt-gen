"""FastAPI 애플리케이션 — lifespan 및 라우터 등록."""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

# sys.path (src/) 설정은 config import 시 실행된다
from server.app.config import ROOT_DIR  # noqa: F401
from server.app import state

logger = logging.getLogger("ppt_gen.server")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Windows ProactorEventLoop가 클라이언트 연결 끊김 시 뱉는 WinError 10054는 무해한 노이즈
if sys.platform == "win32":
    class _WinConnResetFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if "WinError 10054" in record.getMessage():
                return False
            if record.exc_info and record.exc_info[1]:
                if "10054" in str(record.exc_info[1]):
                    return False
            return True
    logging.getLogger("asyncio").addFilter(_WinConnResetFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    from server.app.services.db import init_history_db
    from server.app.services.template_service import template_sync_loop

    try:
        init_history_db()
        logger.info("[startup] DB 초기화 완료")
    except Exception as e:
        logger.warning("[startup] DB 초기화 실패 (무시하고 계속): %s", e)

    try:
        from server.app.services.auth_service import cleanup_expired_sessions
        removed = cleanup_expired_sessions()
        if removed:
            logger.info("[startup] 만료 세션 %d건 삭제", removed)
    except Exception as e:
        logger.warning("[startup] 만료 세션 정리 실패 (무시): %s", e)

    # asyncio.Lock은 이벤트 루프 안에서만 생성 가능
    app.state.songlist_lock = asyncio.Lock()

    state.template_sync_task = asyncio.create_task(template_sync_loop())
    logger.info("[startup] 템플릿 동기화 태스크 시작됨")

    yield

    # shutdown
    if state.template_sync_task and not state.template_sync_task.done():
        state.template_sync_task.cancel()
        try:
            await state.template_sync_task
        except asyncio.CancelledError:
            pass
    state.executor.shutdown(wait=False)
    state.template_executor.shutdown(wait=False)
    logger.info("[shutdown] 종료 완료")


def create_app() -> FastAPI:
    import os
    from fastapi.middleware.cors import CORSMiddleware
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from server.app.api import health, lyrics, history, exports, errors, jobs, templates, auth, graph
    from server.app.api.rate_limit import limiter

    app = FastAPI(title="PO,RR PPT Gen Server", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS — PORR_CORS_ORIGINS 환경변수로 제어 (기본: Vite dev server)
    from server.app.config import CORS_ORIGINS
    if CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(lyrics.router)
    app.include_router(history.router)
    app.include_router(graph.router)
    app.include_router(templates.router)
    app.include_router(exports.router)
    app.include_router(errors.router)
    app.include_router(jobs.router)

    # React 웹앱 서빙 — API 라우터 등록 후 마지막에 추가
    web_dist = os.path.join(ROOT_DIR, "apps", "web", "dist")
    if os.path.isdir(web_dist):
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles

        # /assets/, /favicon.ico 등 실제 파일은 StaticFiles 로 서빙
        assets_dir = os.path.join(web_dist, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # 그 외 모든 경로 → index.html (SPA 클라이언트 라우팅)
        index_html = os.path.join(web_dist, "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # 루트 레벨 실제 파일(favicon.ico 등) 먼저 확인
            candidate = os.path.join(web_dist, full_path)
            if os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(index_html)

        logger.info("[startup] 웹앱 정적 파일 서빙: %s", web_dist)

    return app


app = create_app()
