from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SongEntry:
    title: str
    sequence: str
    lyrics: str | None = None


@dataclass
class PptSettings:
    max_lines_per_slide: int = 4
    max_chars_per_line: int = 18
    lyrics_font_size: float | None = None


@dataclass
class PptGeneratePayload:
    songs: list[SongEntry] = field(default_factory=list)
    settings: PptSettings = field(default_factory=PptSettings)
    template_id: str | None = None
    template_path: str | None = None
