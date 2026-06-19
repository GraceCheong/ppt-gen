import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from error_reporter import build_error_report, _trim


class TestTrim:
    def test_short_text_unchanged(self):
        assert _trim("hello", 100) == "hello"

    def test_long_text_truncated(self):
        text = "x" * 200
        result = _trim(text, 100)
        # _trim returns text[:limit] + "\n...[trimmed]" — total = limit + 13
        assert result.startswith("x" * 100)
        assert result.endswith("...[trimmed]")

    def test_none_returns_empty(self):
        assert _trim(None, 100) == ""


class TestBuildErrorReport:
    def test_required_fields_present(self):
        report = build_error_report("test_context", "test error message")

        assert report["context"] == "test_context"
        assert report["message"] == "test error message"
        assert "reported_at" in report
        assert "runtime" in report

    def test_runtime_fields(self):
        report = build_error_report("ctx", "boom")

        runtime = report["runtime"]
        assert "python" in runtime
        assert "platform" in runtime
        assert "frozen" in runtime

    def test_extra_included(self):
        report = build_error_report("ctx", "boom", extra={"key": "val"})
        assert report["extra"]["key"] == "val"

    def test_no_lyrics_in_report(self):
        """가사 원문이 report에 포함되지 않는지 확인 (개인정보 보호)."""
        lyrics_text = "비밀 가사 내용"
        report = build_error_report("ctx", "some error", extra={"unrelated": "data"})

        # lyrics_text should NOT appear in report anywhere
        report_str = str(report)
        assert lyrics_text not in report_str
