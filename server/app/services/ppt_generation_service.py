"""PPT 생성 서비스 — ppt_service 래퍼."""
from __future__ import annotations

# config를 먼저 import해서 sys.path(src/) 설정을 보장한다
from server.app.config import GENERATOR_VERSION  # noqa: F401


def build_integrated_pptx(
    template_path: str,
    sequence_entries: list[tuple[str, str]],
    lyrics_by_title: dict,
    output_path: str,
    max_lines_per_slide: int,
    max_chars_per_line: int,
    lyrics_font_size,
) -> dict:
    from ppt_service import build_integrated_pptx as _build
    return _build(
        template_path,
        sequence_entries,
        lyrics_by_title,
        output_path,
        max_lines_per_slide,
        max_chars_per_line,
        lyrics_font_size,
    )
