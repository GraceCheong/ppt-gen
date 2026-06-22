from __future__ import annotations

from porr_core.sequence import split_sequence, find_trailing_repeat_indices


def estimate_slide_count(
    repertoire_entries: list[tuple[str, str]],
    lyrics_by_title: dict[str, str],
    max_lines_per_slide: int,
    max_chars_per_line: int,
) -> int:
    """ppt_builder.append_lyrics_to_ppt 로직을 미러링해 예상 슬라이드 수를 계산한다.

    오프닝 2장 + 각 곡 제목 1장 + 가사 청크 합산 + 클로징 1장.
    마지막 연속 반복(skip_indices) 및 max_lines/max_chars chunking 반영.
    """
    from ppt_builder import parse_lyrics_text, get_base_key, wrap_text_by_max_chars, chunk_text

    total = 2  # 오프닝 슬라이드 2장 (홈 + 예배를 시작하며)

    for title, seq_str in repertoire_entries:
        if not seq_str.strip():
            total += 1  # 제목 슬라이드만
            continue

        lyrics_text = lyrics_by_title.get(title, "")
        lyrics_dict = parse_lyrics_text(lyrics_text) if lyrics_text.strip() else {}

        seq_parts = split_sequence(seq_str)
        skip_indices = find_trailing_repeat_indices(seq_parts)

        total += 1  # 곡 제목 슬라이드

        for idx, part in enumerate(seq_parts):
            if idx in skip_indices:
                continue
            base_part = get_base_key(part)

            if part in lyrics_dict:
                text = lyrics_dict[part]
            elif base_part in lyrics_dict:
                text = lyrics_dict[base_part]
            else:
                if idx == 0 and base_part.upper() in ("I", "INTRO"):
                    continue
                text = "-"

            text = wrap_text_by_max_chars(text, max_chars_per_line)
            chunks = chunk_text(text, max_lines_per_slide) or [""]
            total += len(chunks)

    total += 1  # 클로징 슬라이드 (기도)
    return total
