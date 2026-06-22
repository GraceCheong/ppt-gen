import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from porr_core.slide_estimator import estimate_slide_count


_SAMPLE_LYRICS = """\
I

V1
나의 사랑
너는 어여쁘고 참 귀하다
어느 보석보다 귀하다

V2
주의 사랑
이 사랑은 결코 변치 않아

C
주님의 나라와 뜻이
나의 삶 속에 임하시며
주님 알기를 주만 보기를 소망해
"""


class TestEstimateSlideCount:
    def test_no_songs(self):
        # 오프닝 2장 + 클로징 1장 = 3장
        result = estimate_slide_count([], {}, 4, 18)
        assert result == 3

    def test_single_song_no_lyrics(self):
        # 오프닝 2 + 제목 1 + 파트별("-" 한 장씩) + 클로징 1
        entries = [("한나의 노래", "I-V1-C")]
        result = estimate_slide_count(entries, {}, 4, 18)
        # I(idx=0, intro → skip), V1(-), C(-) = 2 lyrics slides + 1 title = 3
        # total = 2(opening) + 3 + 1(closing) = 6
        assert result == 6

    def test_intro_skipped_when_no_lyrics(self):
        # I가 첫 파트이고 가사 없으면 건너뜀
        entries = [("테스트", "I-V1")]
        result = estimate_slide_count(entries, {}, 4, 18)
        # I skip, V1("-") = 1 slide + title = 2
        # total = 2 + 2 + 1 = 5
        assert result == 5

    def test_trailing_repeat_counted_once(self):
        # C-C 마지막 반복 → 두 번째 C 슬라이드 생략
        entries = [("한나의 노래", "I-V1-C-C")]
        result_no_repeat = estimate_slide_count(entries, {}, 4, 18)
        entries_no_repeat = [("한나의 노래", "I-V1-C")]
        result_one_c = estimate_slide_count(entries_no_repeat, {}, 4, 18)
        # C-C 는 C 한 장만 생성하므로 결과가 같아야 함
        assert result_no_repeat == result_one_c

    def test_with_lyrics(self):
        entries = [("한나의 노래", "I-V1-V2-C")]
        lyrics = {"한나의 노래": _SAMPLE_LYRICS}
        result = estimate_slide_count(entries, lyrics, 4, 18)
        # I = lyrics_dict에 존재(빈 내용) → 빈 슬라이드 1장 (ppt_builder 동일 동작)
        # V1 = 3 lines → 1 chunk (max_lines=4)
        # V2 = 2 lines → 1 chunk
        # C = 3 lines → 1 chunk
        # title(1) + I(1) + V1(1) + V2(1) + C(1) = 5 slides per song
        # total = 2(opening) + 5 + 1(closing) = 8
        assert result == 8

    def test_opening_and_closing_always_present(self):
        result = estimate_slide_count([], {}, 4, 18)
        assert result == 3  # 2 opening + 1 closing

    def test_consistency_with_trailing_repeat(self):
        """마지막 연속 반복 규칙: I-V1-V2-C-C는 I-V1-V2-C와 슬라이드 수가 같아야 한다."""
        entries_repeat = [("테스트", "I-V1-V2-C-C")]
        entries_single = [("테스트", "I-V1-V2-C")]
        assert (
            estimate_slide_count(entries_repeat, {}, 4, 18)
            == estimate_slide_count(entries_single, {}, 4, 18)
        )

    def test_mid_repeat_not_skipped(self):
        """중간 반복은 skip하지 않는다: I-V1-V1-C는 I-V1-C와 슬라이드 수가 달라야 한다."""
        entries_mid_repeat = [("테스트", "I-V1-V1-C")]
        entries_no_repeat = [("테스트", "I-V1-C")]
        assert (
            estimate_slide_count(entries_mid_repeat, {}, 4, 18)
            > estimate_slide_count(entries_no_repeat, {}, 4, 18)
        )
