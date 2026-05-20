import re


def parse_lyrics_text(raw_text):
    lyrics_dict = {}
    blocks = re.split(r'\n\s*\n', raw_text.strip())

    for block in blocks:
        lines = block.strip().split('\n')
        if not lines:
            continue

        part_key = lines[0].strip()
        lyrics_content = '\n'.join([line.strip() for line in lines[1:]])
        lyrics_dict[part_key] = lyrics_content

    return lyrics_dict


def get_base_key(part_key):
    return re.sub(r"'+$", "", part_key)


def chunk_text(text, max_lines=2):
    if not text:
        return []
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    MIN_LINE_THRESHOLD = 6

    chunks = []
    i = 0
    while i < len(lines):
        take_lines = max_lines
        if max_lines == 1 and len(lines[i]) <= MIN_LINE_THRESHOLD and i + 1 < len(lines):
            take_lines = 2

        chunk_lines = lines[i:i + take_lines]
        chunks.append('\n'.join(chunk_lines))
        i += len(chunk_lines)

    return chunks


def set_editable_text(shape, text):
    text_frame = shape.text_frame
    text_frame.clear()

    lines = text.split('\n') if text else [""]
    for idx, line in enumerate(lines):
        paragraph = text_frame.paragraphs[0] if idx == 0 else text_frame.add_paragraph()
        run = paragraph.add_run()
        run.text = line


def parse_sequence_text(sequence_text):
    lines = [line.strip() for line in sequence_text.splitlines() if line.strip()]

    if not lines:
        raise ValueError("레파토리 입력창이 비어 있습니다.")

    if len(lines) % 2 != 0:
        raise ValueError(f"'{lines[-1]}' 다음에 진행 순서 줄이 없습니다.")

    sequence_entries = []
    for i in range(0, len(lines), 2):
        song_title = lines[i]
        sequence_str = lines[i + 1]

        if not song_title:
            raise ValueError(f"{i + 1}번째 줄의 곡 제목이 비어 있습니다.")
        if not sequence_str:
            raise ValueError(f"'{song_title}'의 진행 순서가 비어 있습니다.")

        sequence_entries.append((song_title, sequence_str))

    return sequence_entries


def append_lyrics_to_ppt(prs, song_title, lyrics_text, sequence_str, max_lines_per_slide=2):
    lyrics_dict = parse_lyrics_text(lyrics_text)
    sequence_list = [part.strip() for part in sequence_str.split('-') if part.strip()]

    title_layout = None
    lyrics_layout = None

    for layout in prs.slide_layouts:
        if "제목" in layout.name:
            title_layout = layout
        if "가사" in layout.name:
            lyrics_layout = layout

    if title_layout is None:
        title_layout = prs.slide_layouts[2] if len(prs.slide_layouts) > 2 else prs.slide_layouts[0]
    if lyrics_layout is None:
        lyrics_layout = prs.slide_layouts[3] if len(prs.slide_layouts) > 3 else prs.slide_layouts[0]

    title_slide = prs.slides.add_slide(title_layout)
    for shape in title_slide.placeholders:
        if shape.has_text_frame:
            set_editable_text(shape, song_title)
            break

    for idx, part in enumerate(sequence_list):
        base_part = get_base_key(part)

        if part in lyrics_dict:
            display_text = lyrics_dict[part]
        elif base_part in lyrics_dict:
            display_text = lyrics_dict[base_part]
        else:
            if part.startswith('(') and part.endswith(')'):
                display_text = part[1:-1].strip()
            else:
                if idx == 0 and base_part.upper() in ["I", "INTRO"]:
                    continue
                display_text = "-"

        chunks = chunk_text(display_text, max_lines_per_slide)
        if not chunks:
            chunks = [""]

        for chunk in chunks:
            slide = prs.slides.add_slide(lyrics_layout)

            placeholders = [shape for shape in slide.placeholders if shape.has_text_frame]
            placeholders.sort(key=lambda s: getattr(s, 'width', 0) * getattr(s, 'height', 0), reverse=True)

            lyrics_placeholder = placeholders[0] if len(placeholders) > 0 else None
            song_title_placeholder = placeholders[1] if len(placeholders) > 1 else None

            if lyrics_placeholder is not None:
                set_editable_text(lyrics_placeholder, chunk)

            if song_title_placeholder is not None:
                set_editable_text(song_title_placeholder, song_title)
