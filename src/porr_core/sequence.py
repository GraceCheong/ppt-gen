from __future__ import annotations


def split_sequence(sequence: str) -> list[str]:
    return [p.strip() for p in str(sequence or "").split("-") if p.strip()]


def normalize_sequence(sequence: str) -> str:
    parts = split_sequence(sequence)
    normalized = [p[0].upper() + p[1:] if p else p for p in parts]
    return "-".join(normalized)


def find_trailing_repeat_indices(parts: list[str]) -> set[int]:
    """마지막 연속 반복 그룹의 두 번째~끝 인덱스를 반환한다.

    예: ["I", "V1", "C", "C"]   → {3}      (마지막 C-C 중 2번째 C)
    예: ["I", "V1", "V1", "C"]  → set()    (중간 반복은 해당 없음)
    예: ["V1", "C", "C", "C"]   → {2, 3}   (마지막 C-C-C 중 2~3번째)
    """
    if len(parts) < 2 or parts[-1] != parts[-2]:
        return set()
    trail = parts[-1]
    start = len(parts) - 1
    while start > 0 and parts[start - 1] == trail:
        start -= 1
    return set(range(start + 1, len(parts)))
