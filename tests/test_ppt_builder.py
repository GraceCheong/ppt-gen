import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from ppt_builder import (
    parse_lyrics_text,
    chunk_text,
    wrap_text_by_max_chars,
    parse_sequence_text,
    get_base_key,
)


# ---------------------------------------------------------------------------
# parse_lyrics_text
# ---------------------------------------------------------------------------

class TestParseLyricsText:
    def test_single_part(self):
        raw = "verse\nline1\nline2"
        result = parse_lyrics_text(raw)
        assert result == {"verse": "line1\nline2"}

    def test_multiple_parts(self):
        raw = "verse\nline1\n\nchorus\nline2\nline3"
        result = parse_lyrics_text(raw)
        assert result["verse"] == "line1"
        assert result["chorus"] == "line2\nline3"

    def test_empty_input(self):
        assert parse_lyrics_text("") == {}

    def test_strips_whitespace(self):
        raw = "  verse  \n  line1  \nline2  "
        result = parse_lyrics_text(raw)
        assert "verse" in result


# ---------------------------------------------------------------------------
# get_base_key
# ---------------------------------------------------------------------------

class TestGetBaseKey:
    def test_no_prime(self):
        assert get_base_key("verse") == "verse"

    def test_single_prime(self):
        assert get_base_key("verse'") == "verse"

    def test_multiple_primes(self):
        assert get_base_key("chorus''") == "chorus"

    def test_prime_in_middle_unchanged(self):
        assert get_base_key("it's") == "it's"


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_empty(self):
        assert chunk_text("") == []

    def test_single_line(self):
        assert chunk_text("hello") == ["hello"]

    def test_splits_by_max_lines(self):
        text = "a\nb\nc\nd"
        chunks = chunk_text(text, max_lines=2)
        assert chunks == ["a\nb", "c\nd"]

    def test_odd_lines(self):
        text = "a\nb\nc"
        chunks = chunk_text(text, max_lines=2)
        assert len(chunks) == 2
        assert chunks[0] == "a\nb"
        assert chunks[1] == "c"

    def test_short_line_merges_when_max_1(self):
        # Lines shorter than _MIN_SHORT_LINE_LEN (6) should merge when max_lines=1
        text = "hi\nworld"
        chunks = chunk_text(text, max_lines=1)
        # "hi" is short (len 2 <= 6), so it grabs the next line too
        assert chunks == ["hi\nworld"]

    def test_long_line_stays_alone_with_max_1(self):
        text = "longline\nnext"
        chunks = chunk_text(text, max_lines=1)
        assert chunks[0] == "longline"
        assert chunks[1] == "next"

    def test_blank_lines_filtered(self):
        text = "a\n\nb"
        chunks = chunk_text(text, max_lines=2)
        assert chunks == ["a\nb"]


# ---------------------------------------------------------------------------
# wrap_text_by_max_chars
# ---------------------------------------------------------------------------

class TestWrapTextByMaxChars:
    def test_no_wrap_needed(self):
        assert wrap_text_by_max_chars("hello", 10) == "hello"

    def test_wraps_long_line(self):
        text = "a" * 20
        result = wrap_text_by_max_chars(text, max_chars_per_line=10)
        for line in result.split("\n"):
            assert len(line) <= 10

    def test_prefers_space_break(self):
        text = "hello world long"
        result = wrap_text_by_max_chars(text, max_chars_per_line=11)
        assert "hello world" in result.split("\n")[0]

    def test_empty_input(self):
        assert wrap_text_by_max_chars("", 10) == ""

    def test_zero_max_chars_returns_unchanged(self):
        assert wrap_text_by_max_chars("hello", 0) == "hello"

    def test_invalid_max_chars_uses_default(self):
        result = wrap_text_by_max_chars("a" * 30, max_chars_per_line="bad")
        # Falls back to 18
        for line in result.split("\n"):
            assert len(line) <= 18

    def test_multiline_input(self):
        text = "line one\nline two"
        result = wrap_text_by_max_chars(text, max_chars_per_line=20)
        assert "line one" in result
        assert "line two" in result


# ---------------------------------------------------------------------------
# parse_sequence_text
# ---------------------------------------------------------------------------

class TestParseSequenceText:
    def test_valid_two_songs(self):
        text = "Amazing Grace\nV-C-V-C\nHoly Holy\nV-C"
        result = parse_sequence_text(text)
        assert result == [("Amazing Grace", "V-C-V-C"), ("Holy Holy", "V-C")]

    def test_single_song(self):
        text = "Song\nV-C"
        result = parse_sequence_text(text)
        assert result == [("Song", "V-C")]

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="비어 있습니다"):
            parse_sequence_text("")

    def test_odd_lines_raises(self):
        with pytest.raises(ValueError):
            parse_sequence_text("Song\nV-C\nOrphan")

    def test_strips_whitespace(self):
        text = "  Song  \n  V-C  "
        result = parse_sequence_text(text)
        assert result[0] == ("Song", "V-C")

    def test_ignores_blank_lines(self):
        text = "Song\nV-C\n\nSong2\nC-V"
        result = parse_sequence_text(text)
        assert len(result) == 2
