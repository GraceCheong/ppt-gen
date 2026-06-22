"""템플릿 파일 관리 및 Google Drive 동기화 서비스."""
from __future__ import annotations

import asyncio
import logging
import os

from server.app.config import ROOT_DIR, TEMPLATE_SYNC_INTERVAL_SECONDS

logger = logging.getLogger("ppt_gen.server")


def _server_template_dir() -> str:
    from constants import ASSETS_DIR_NAME, TEMPLATE_DIR_NAME
    path = os.path.join(ROOT_DIR, ASSETS_DIR_NAME, TEMPLATE_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def server_template_files() -> set[str]:
    template_dir = _server_template_dir()
    result = set()
    for root, _, files in os.walk(template_dir):
        for file_name in files:
            if file_name.lower().endswith(".pptx"):
                result.add(os.path.abspath(os.path.join(root, file_name)))
    return result


def server_songlist_template_path() -> str:
    return os.path.join(_server_template_dir(), "songlist_template.pptx")


def list_template_names() -> list[str]:
    return sorted(
        os.path.basename(p)
        for p in server_template_files()
        if os.path.basename(p).lower() != "songlist_template.pptx"
    )


def resolve_template_path(template_id: str | None) -> str:
    """template_id로 서버 템플릿 파일 경로를 반환한다. 없으면 FileNotFoundError."""
    template_dir = _server_template_dir()

    if template_id:
        candidate = template_id if template_id.lower().endswith(".pptx") else f"{template_id}.pptx"
        path = os.path.join(template_dir, candidate)
        if os.path.exists(path):
            return path

    files = sorted(server_template_files())
    if files:
        return files[0]

    raise FileNotFoundError(
        f"템플릿을 찾을 수 없습니다 (template_id={template_id!r}). "
        "서버 템플릿 동기화 후 다시 시도해 주세요."
    )


def resolve_songlist_template_path(template_id: str | None = None) -> str:
    """songlist 카드용 템플릿 경로를 반환한다. 없으면 FileNotFoundError."""
    template_dir = _server_template_dir()

    if template_id:
        candidate = template_id if template_id.lower().endswith(".pptx") else f"{template_id}.pptx"
        path = os.path.join(template_dir, candidate)
        if os.path.exists(path):
            return path

    default = os.path.join(template_dir, "songlist_template.pptx")
    if os.path.exists(default):
        return default

    raise FileNotFoundError(
        "songlist_template.pptx를 찾을 수 없습니다. "
        "서버 템플릿 동기화 후 다시 시도해 주세요."
    )


def sync_templates_once() -> list[str]:
    import gdown
    from constants import TEMPLATE_DOWNLOAD_URL

    template_dir = _server_template_dir()
    before = server_template_files()

    try:
        gdown.download_folder(
            TEMPLATE_DOWNLOAD_URL,
            output=template_dir,
            quiet=True,
            use_cookies=False,
            resume=True,
            remaining_ok=True,
        )
    except TypeError:
        gdown.download_folder(
            TEMPLATE_DOWNLOAD_URL,
            output=template_dir,
            quiet=True,
            use_cookies=False,
            resume=True,
        )

    after = server_template_files()
    return sorted(os.path.basename(path) for path in after - before)


async def template_sync_loop() -> None:
    from server.app import state

    while True:
        try:
            loop = asyncio.get_event_loop()
            added = await loop.run_in_executor(state.template_executor, sync_templates_once)
            if added:
                logger.info(
                    "[template-sync] 새 템플릿 %d개 다운로드: %s",
                    len(added),
                    ", ".join(added),
                )
            else:
                logger.debug("[template-sync] 새 템플릿 없음")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[template-sync] 템플릿 확인 실패: %s", e)

        await asyncio.sleep(TEMPLATE_SYNC_INTERVAL_SECONDS)
