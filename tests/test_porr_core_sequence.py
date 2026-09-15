import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from porr_core.sequence import (
    split_sequence,
    normalize_sequence,
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
