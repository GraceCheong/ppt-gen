from pathlib import Path
import sys

import requests


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ppt_server_client import PptServerUnavailable, generate_songlist_card_via_server


class _MockResponse:
    def __init__(self, status_code=200, content=b"png", headers=None, text=""):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.text = text

    def json(self):
        raise ValueError("no json")


def test_songlist_card_retries_legacy_endpoint(monkeypatch, tmp_path):
    calls = []

    def _mock_post(url, data, files, timeout):
        calls.append(url)
        if url.endswith("/songlist-card"):
            return _MockResponse(status_code=404, text="Not Found")
        if url.endswith("/songlist"):
            return _MockResponse(status_code=200, headers={"X-Week-Number": "23"})
        return _MockResponse(status_code=404, text="Not Found")

    monkeypatch.setattr(requests, "post", _mock_post)

    template_path = tmp_path / "songlist.pptx"
    template_path.write_bytes(b"dummy pptx")
    output_path = tmp_path / "songlist_card.png"

    week_num = generate_songlist_card_via_server(
        "http://example.com",
        str(template_path),
        ["Song A", "Song B"],
        str(output_path),
    )

    assert week_num == 23
    assert output_path.exists()
    assert calls[:2] == [
        "http://example.com/songlist-card",
        "http://example.com/songlist",
    ]


def test_songlist_card_does_not_retry_after_timeout(monkeypatch, tmp_path):
    calls = []

    def _mock_post(url, data, files, timeout):
        calls.append(url)
        raise requests.Timeout("read timed out")

    monkeypatch.setattr(requests, "post", _mock_post)

    template_path = tmp_path / "songlist.pptx"
    template_path.write_bytes(b"dummy pptx")
    output_path = tmp_path / "songlist_card.png"

    try:
        generate_songlist_card_via_server(
            "http://example.com",
            str(template_path),
            ["Song A", "Song B"],
            str(output_path),
        )
    except PptServerUnavailable as exc:
        assert "endpoint=/songlist-card" in str(exc)
    else:
        raise AssertionError("PptServerUnavailable was not raised")

    assert calls == ["http://example.com/songlist-card"]
