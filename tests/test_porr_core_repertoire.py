import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from porr_core.repertoire import (
    clean_repertoire_title,
    normalize_repertoire_entries,
    format_repertoire_entries,
    sequence_text_from_entries,
)


class TestCleanRepertoireTitle:
    def test_removes_number_dot_prefix(self):
        assert clean_repertoire_title("1. 한나의 노래") == "한나의 노래"

    def test_removes_number_paren_prefix(self):
        assert clean_repertoire_title("2) 감사해") == "감사해"

    def test_removes_number_close_paren_prefix(self):
        assert clean_repertoire_title("3. 주님의 이름") == "주님의 이름"

    def test_no_prefix_unchanged(self):
        assert clean_repertoire_title("한나의 노래") == "한나의 노래"

    def test_empty_string(self):
        assert clean_repertoire_title("") == ""

    def test_strips_whitespace(self):
        assert clean_repertoire_title("  한나의 노래  ") == "한나의 노래"

    def test_none_value(self):
        assert clean_repertoire_title(None) == ""

    def test_two_digit_number_prefix(self):
        assert clean_repertoire_title("10. 주를 찬양") == "주를 찬양"


class TestNormalizeRepertoireEntries:
    def test_parses_two_line_pairs(self):
        raw = "한나의 노래\nI-V1-V2-C-C\n감사해\nV1-C-C"
        result = normalize_repertoire_entries(raw)
        assert result == [
            ("한나의 노래", "I-V1-V2-C-C"),
            ("감사해", "V1-C-C"),
        ]

    def test_strips_number_prefix_from_title(self):
        raw = "1. 한나의 노래\nI-V1-V2-C\n2) 감사해\nV1-C"
        result = normalize_repertoire_entries(raw)
        assert result == [
            ("한나의 노래", "I-V1-V2-C"),
            ("감사해", "V1-C"),
        ]

    def test_single_song(self):
        raw = "주님의 이름\nV1-C"
        assert normalize_repertoire_entries(raw) == [("주님의 이름", "V1-C")]

    def test_empty_string(self):
        assert normalize_repertoire_entries("") == []

    def test_blank_lines_ignored(self):
        raw = "\n한나의 노래\nI-V1\n\n"
        result = normalize_repertoire_entries(raw)
        assert result == [("한나의 노래", "I-V1")]

    def test_odd_line_count_ignores_trailing(self):
        raw = "한나의 노래\nI-V1\n혼자남은제목"
        result = normalize_repertoire_entries(raw)
        assert result == [("한나의 노래", "I-V1")]


class TestFormatRepertoireEntries:
    def test_formats_single_entry(self):
        entries = [("한나의 노래", "I-V1-V2-C")]
        assert format_repertoire_entries(entries) == "한나의 노래\nI-V1-V2-C"

    def test_formats_multiple_entries(self):
        entries = [("한나의 노래", "I-V1"), ("감사해", "V1-C")]
        result = format_repertoire_entries(entries)
        assert result == "한나의 노래\nI-V1\n감사해\nV1-C"

    def test_empty_list(self):
        assert format_repertoire_entries([]) == ""


class TestSequenceTextFromEntries:
    def test_basic_conversion(self):
        entries = [
            {"title": "한나의 노래", "sequence": "I-V1-V2-C"},
            {"title": "감사해", "sequence": "V1-C"},
        ]
        result = sequence_text_from_entries(entries)
        assert result == "한나의 노래\nI-V1-V2-C\n\n감사해\nV1-C"

    def test_skips_non_dict_entries(self):
        entries = [{"title": "한나의 노래", "sequence": "I-V1"}, "not a dict"]
        result = sequence_text_from_entries(entries)
        assert result == "한나의 노래\nI-V1"

    def test_skips_empty_title_or_sequence(self):
        entries = [
            {"title": "", "sequence": "I-V1"},
            {"title": "감사해", "sequence": ""},
            {"title": "한나의 노래", "sequence": "I-V1"},
        ]
        result = sequence_text_from_entries(entries)
        assert result == "한나의 노래\nI-V1"

    def test_empty_list(self):
        assert sequence_text_from_entries([]) == ""
