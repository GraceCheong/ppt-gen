import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from porr_core.sequence import (
    split_sequence,
    normalize_sequence,
    find_trailing_repeat_indices,
)


class TestSplitSequence:
    def test_basic_split(self):
        assert split_sequence("I-V1-V2-C") == ["I", "V1", "V2", "C"]

    def test_strips_whitespace(self):
        assert split_sequence("I - V1 - C") == ["I", "V1", "C"]

    def test_empty_string(self):
        assert split_sequence("") == []

    def test_none_value(self):
        assert split_sequence(None) == []

    def test_single_part(self):
        assert split_sequence("V1") == ["V1"]

    def test_trailing_dash_ignored(self):
        assert split_sequence("I-V1-C-") == ["I", "V1", "C"]


class TestNormalizeSequence:
    def test_uppercases_first_char_of_each_part(self):
        # 각 파트의 첫 글자를 대문자로 변환
        assert normalize_sequence("i-v1-c") == "I-V1-C"

    def test_already_normalized(self):
        assert normalize_sequence("I-V1-C") == "I-V1-C"

    def test_empty(self):
        assert normalize_sequence("") == ""


class TestFindTrailingRepeatIndices:
    def test_single_trailing_repeat(self):
        # I-V1-C-C → 마지막 C-C 중 두 번째 C
        assert find_trailing_repeat_indices(["I", "V1", "C", "C"]) == {3}

    def test_no_trailing_repeat(self):
        # I-V1-V1-C → 중간 반복이므로 해당 없음
        assert find_trailing_repeat_indices(["I", "V1", "V1", "C"]) == set()

    def test_triple_trailing_repeat(self):
        # V1-C-C-C → 마지막 C-C-C 중 2~3번째
        assert find_trailing_repeat_indices(["V1", "C", "C", "C"]) == {2, 3}

    def test_no_repeat_at_all(self):
        assert find_trailing_repeat_indices(["I", "V1", "C"]) == set()

    def test_empty_list(self):
        assert find_trailing_repeat_indices([]) == set()

    def test_single_element(self):
        assert find_trailing_repeat_indices(["C"]) == set()

    def test_all_same(self):
        # C-C-C → 첫 번째만 남기고 나머지 skip
        assert find_trailing_repeat_indices(["C", "C", "C"]) == {1, 2}

    def test_mid_repeat_then_different(self):
        # I-C-C-B → C-C는 중간 반복, 마지막이 다름 → skip 없음
        assert find_trailing_repeat_indices(["I", "C", "C", "B"]) == set()
