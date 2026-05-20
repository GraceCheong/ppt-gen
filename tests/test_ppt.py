from pathlib import Path
import sys

from pptx import Presentation


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from lyrics_to_ppt import append_lyrics_to_ppt, chunk_text, parse_lyrics_text


SAMPLE_LYRICS = """V1
가사 첫 번째 줄
가사 두 번째 줄

C
후렴 첫 번째 줄
후렴 두 번째 줄

Out
마지막 가사"""


def test_parse_lyrics_text():
    parsed = parse_lyrics_text(SAMPLE_LYRICS)

    assert parsed["V1"] == "가사 첫 번째 줄\n가사 두 번째 줄"
    assert parsed["C"] == "후렴 첫 번째 줄\n후렴 두 번째 줄"
    assert parsed["Out"] == "마지막 가사"


def test_chunk_text_respects_max_lines():
    chunks = chunk_text("첫 줄\n둘째 줄\n셋째 줄", max_lines=2)

    assert chunks == ["첫 줄\n둘째 줄", "셋째 줄"]


def test_append_lyrics_to_ppt_adds_slides():
    prs = Presentation(str(ROOT_DIR / "template.pptx"))
    before_count = len(prs.slides)

    append_lyrics_to_ppt(
        prs,
        "테스트 곡",
        SAMPLE_LYRICS,
        "I-V1-C-Out",
        max_lines_per_slide=2,
        long_line_threshold=18,
    )

    assert len(prs.slides) > before_count


def test_append_lyrics_to_ppt_keeps_user_selected_four_line_chunks():
    prs = Presentation(str(ROOT_DIR / "template.pptx"))
    before_count = len(prs.slides)
    long_lyrics = """V
이 줄은 긴 줄 기준보다 충분히 긴 가사입니다
둘째 줄
셋째 줄
넷째 줄"""

    append_lyrics_to_ppt(
        prs,
        "네 줄 테스트",
        long_lyrics,
        "V",
        max_lines_per_slide=4,
        long_line_threshold=18,
    )

    assert len(prs.slides) == before_count + 2
