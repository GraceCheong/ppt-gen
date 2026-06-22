"""송리스트 카드 PNG 생성 서비스."""
from __future__ import annotations

from server.app.config import GENERATOR_VERSION  # noqa: F401 — ensures sys.path is set


def build_songlist_card_png(
    template_path: str,
    song_titles: list[str],
    output_path: str,
) -> int:
    from ppt_service import build_songlist_card_png as _build
    return _build(template_path, song_titles, output_path)
