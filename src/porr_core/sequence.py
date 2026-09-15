from __future__ import annotations


def split_sequence(sequence: str) -> list[str]:
    return [p.strip() for p in str(sequence or "").split("-") if p.strip()]


def normalize_sequence(sequence: str) -> str:
    parts = split_sequence(sequence)
    normalized = [p[0].upper() + p[1:] if p else p for p in parts]
    return "-".join(normalized)
