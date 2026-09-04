import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from lxml import etree
from pptx.enum.shapes import PP_PLACEHOLDER
from ppt_builder import (
    _character_properties_from_text_body,
    _default_theme_run_properties,
    _ensure_script_fonts,
    parse_lyrics_text,
    chunk_text,
    wrap_text_by_max_chars,
    parse_sequence_text,
    get_base_key,
)


A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def a(tag):
    return f"{{{A_NS}}}{tag}"


class TestFontPreservation:
    def test_reads_font_from_end_paragraph_properties(self):
        tx_body = etree.fromstring(
            f'''<a:txBody xmlns:a="{A_NS}">
              <a:bodyPr/><a:lstStyle/>
              <a:p><a:endParaRPr lang="ko-KR" sz="3200">
                <a:latin typeface="나눔스퀘어"/>
              </a:endParaRPr></a:p>
            </a:txBody>'''.encode()
        )

        props = _character_properties_from_text_body(tx_body)

        assert props.tag == a("rPr")
        assert props.get("sz") == "3200"
        assert props.find(a("latin")).get("typeface") == "나눔스퀘어"

    def test_reads_font_from_list_style_default_properties(self):
        tx_body = etree.fromstring(
            f'''<a:txBody xmlns:a="{A_NS}">
              <a:bodyPr/>
              <a:lstStyle><a:lvl1pPr><a:defRPr sz="2800">
                <a:ea typeface="Pretendard"/>
              </a:defRPr></a:lvl1pPr></a:lstStyle>
              <a:p/>
            </a:txBody>'''.encode()
        )

        props = _character_properties_from_text_body(tx_body)

        assert props.tag == a("rPr")
        assert props.find(a("ea")).get("typeface") == "Pretendard"

    def test_merges_language_from_end_props_with_font_from_list_style(self):
        tx_body = etree.fromstring(
            f'''<a:txBody xmlns:a="{A_NS}">
              <a:bodyPr/>
              <a:lstStyle><a:lvl1pPr><a:defRPr sz="4800">
                <a:latin typeface="Gowun Dodum"/>
                <a:ea typeface="Gowun Dodum"/>
              </a:defRPr></a:lvl1pPr></a:lstStyle>
              <a:p><a:endParaRPr lang="ko-KR" dirty="0"/></a:p>
            </a:txBody>'''.encode()
        )

        props = _character_properties_from_text_body(tx_body)

        assert props.get("lang") == "ko-KR"
        assert props.get("sz") == "4800"
        assert props.find(a("latin")).get("typeface") == "Gowun Dodum"
        assert props.find(a("ea")).get("typeface") == "Gowun Dodum"

    def test_adds_east_asian_and_complex_script_fonts(self):
        props = etree.fromstring(
            f'<a:rPr xmlns:a="{A_NS}"><a:latin typeface="나눔스퀘어"/></a:rPr>'.encode()
        )

        _ensure_script_fonts(props)

        assert props.find(a("ea")).get("typeface") == "나눔스퀘어"
        assert props.find(a("cs")).get("typeface") == "나눔스퀘어"

    def test_maps_latin_theme_token_to_east_asian_theme_token(self):
        props = etree.fromstring(
            f'<a:rPr xmlns:a="{A_NS}"><a:latin typeface="+mj-lt"/></a:rPr>'.encode()
        )

        _ensure_script_fonts(props)

        assert props.find(a("ea")).get("typeface") == "+mj-ea"
        assert props.find(a("cs")).get("typeface") == "+mj-cs"

    @pytest.mark.parametrize(
        ("placeholder_type", "family"),
        [
            (PP_PLACEHOLDER.TITLE, "mj"),
            (PP_PLACEHOLDER.CENTER_TITLE, "mj"),
            (PP_PLACEHOLDER.BODY, "mn"),
        ],
    )
    def test_default_theme_fonts_cover_korean(self, placeholder_type, family):
        props = _default_theme_run_properties(placeholder_type)

        assert props.find(a("latin")).get("typeface") == f"+{family}-lt"
        assert props.find(a("ea")).get("typeface") == f"+{family}-ea"
        assert props.find(a("cs")).get("typeface") == f"+{family}-cs"


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
