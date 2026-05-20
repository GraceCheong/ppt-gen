from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from error_reporter import MAX_TEXT_LENGTH, build_error_report


def test_build_error_report_includes_context_and_settings():
    report = build_error_report(
        context="ppt unknown",
        message="failed",
        traceback_text="trace",
        extra={
            "caller": {"function": "generate_ppt"},
            "settings": {"max_chars_per_line": "18"},
        },
        log_tail=["a", "b"],
    )

    assert report["context"] == "ppt unknown"
    assert report["message"] == "failed"
    assert report["traceback"] == "trace"
    assert report["extra"]["caller"]["function"] == "generate_ppt"
    assert report["extra"]["settings"]["max_chars_per_line"] == "18"
    assert report["log_tail"] == ["a", "b"]
    assert "runtime" in report


def test_build_error_report_trims_large_traceback():
    report = build_error_report(
        context="x",
        message="x",
        traceback_text="a" * (MAX_TEXT_LENGTH + 10),
    )

    assert len(report["traceback"]) <= MAX_TEXT_LENGTH + len("\n...[trimmed]")
    assert report["traceback"].endswith("...[trimmed]")
