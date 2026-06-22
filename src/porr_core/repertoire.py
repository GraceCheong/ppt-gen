from __future__ import annotations

import re


def clean_repertoire_title(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^\s*\d+\s*[\.)]\s*", "", text)
    return text.strip()


def normalize_repertoire_entries(raw_text: str) -> list[tuple[str, str]]:
    lines = [l.strip() for l in str(raw_text or "").splitlines() if l.strip()]
    entries: list[tuple[str, str]] = []
    idx = 0
    while idx + 1 < len(lines):
        title = clean_repertoire_title(lines[idx])
        sequence = lines[idx + 1].strip()
        if title and sequence:
            entries.append((title, sequence))
        idx += 2
    return entries


def format_repertoire_entries(entries: list[tuple[str, str]]) -> str:
    rows = []
    for title, sequence in entries:
        rows.append(str(title).strip())
        rows.append(str(sequence).strip())
    return "\n".join(rows).strip()


def sequence_text_from_entries(seq_entries: list[dict]) -> str:
    chunks = []
    for entry in seq_entries:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title", "")).strip()
        sequence = str(entry.get("sequence", "")).strip()
        if title and sequence:
            chunks.append(f"{title}\n{sequence}")
    return "\n\n".join(chunks).strip()
