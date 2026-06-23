"""비동기 PPT 생성 워커."""
from __future__ import annotations

import asyncio
import logging

from server.app import state
from server.app.jobs.job_models import JobStatus
from server.app.jobs.job_store import update_job
from server.app.services.history_service import index_lyrics_from_snapshot
from server.app.services.ppt_generation_service import build_integrated_pptx
from server.app.storage.local_storage import get_generated_pptx_path

logger = logging.getLogger("ppt_gen.server")


async def run_pptx_job(
    job_id: str,
    template_path: str,
    sequence_entries: list[tuple[str, str]],
    lyrics_by_title: dict,
    max_lines_per_slide: int,
    max_chars_per_line: int,
    lyrics_font_size,
) -> None:
    update_job(
        job_id,
        status=JobStatus.running,
        message="PPT를 생성하는 중입니다.",
        progress=10,
    )
    try:
        output_path = get_generated_pptx_path(job_id)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            state.executor,
            build_integrated_pptx,
            template_path,
            sequence_entries,
            lyrics_by_title,
            output_path,
            max_lines_per_slide,
            max_chars_per_line,
            lyrics_font_size,
        )

        # 가사 카탈로그 색인 (이력 저장과 무관하게 항상 실행)
        try:
            index_lyrics_from_snapshot(sequence_entries, lyrics_by_title)
        except Exception as idx_err:
            logger.warning("[job:%s] 가사 색인 실패: %s", job_id, idx_err)

        update_job(
            job_id,
            status=JobStatus.succeeded,
            progress=100,
            message=f"PPT 생성 완료 ({result['appended_count']}곡)",
            output_path=output_path,
            download_url=f"/api/jobs/{job_id}/download",
        )
        logger.info("[job:%s] succeeded songs=%d", job_id, result["appended_count"])

    except Exception as e:
        logger.error("[job:%s] failed: %s", job_id, e)
        update_job(
            job_id,
            status=JobStatus.failed,
            progress=0,
            message="PPT 생성에 실패했습니다.",
            error=str(e),
        )
