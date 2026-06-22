"""비동기 송리스트 카드 생성 워커."""
from __future__ import annotations

import asyncio
import logging

from server.app import state
from server.app.jobs.job_models import JobStatus
from server.app.jobs.job_store import update_job
from server.app.services.songlist_service import build_songlist_card_png
from server.app.storage.local_storage import get_songlist_card_path

logger = logging.getLogger("ppt_gen.server")


async def run_songlist_job(
    job_id: str,
    template_path: str,
    song_titles: list[str],
) -> None:
    update_job(
        job_id,
        status=JobStatus.running,
        message="송리스트 카드를 생성하는 중입니다.",
        progress=10,
    )
    try:
        output_path = get_songlist_card_path(job_id)
        loop = asyncio.get_event_loop()
        week_num = await loop.run_in_executor(
            state.executor,
            build_songlist_card_png,
            template_path,
            song_titles,
            output_path,
        )
        update_job(
            job_id,
            status=JobStatus.succeeded,
            progress=100,
            message=f"송리스트 카드 생성 완료 ({week_num}주차, {len(song_titles)}곡)",
            output_path=output_path,
            download_url=f"/api/jobs/{job_id}/download",
        )
        logger.info(
            "[job:%s] succeeded week=%d songs=%d", job_id, week_num, len(song_titles)
        )

    except Exception as e:
        logger.error("[job:%s] failed: %s", job_id, e)
        update_job(
            job_id,
            status=JobStatus.failed,
            progress=0,
            message="송리스트 카드 생성에 실패했습니다.",
            error=str(e),
        )
