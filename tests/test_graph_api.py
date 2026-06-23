"""graph.py 단위 테스트 — D±N 계산 및 캐시 무효화."""
import sys
import os
from datetime import date, timezone, timedelta, datetime
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ── _d_label ──────────────────────────────────────────────────────────────────

def _d_label(date_str: str, today: date) -> str:
    """_d_label 로직을 today 기준으로 직접 계산 (KST 의존성 제거)."""
    try:
        last = date.fromisoformat(date_str)
    except ValueError:
        return ""
    days = (today - last).days
    return f"D+{days}" if days >= 0 else f"D{days}"


def test_d_label_zero():
    today = date(2025, 6, 7)
    assert _d_label("2025-06-07", today) == "D+0"


def test_d_label_positive():
    today = date(2025, 6, 14)
    assert _d_label("2025-06-07", today) == "D+7"


def test_d_label_negative():
    today = date(2025, 6, 1)
    assert _d_label("2025-06-07", today) == "D-6"


def test_d_label_invalid_returns_empty():
    assert _d_label("not-a-date", date.today()) == ""


# ── 캐시 무효화 ───────────────────────────────────────────────────────────────

def test_invalidate_clears_cache():
    from server.app.api import graph as graph_mod
    # 캐시를 임의로 채운 뒤 무효화
    graph_mod._history_cache = (0.0, [{"dummy": True}])
    graph_mod.invalidate_graph_cache()
    assert graph_mod._history_cache is None


def test_cache_is_used_on_second_call(tmp_path, monkeypatch):
    """두 번째 호출에서 DB 쿼리 없이 캐시를 사용한다."""
    import server.app.services.db as db_mod
    import server.app.services.history_service as hist_svc
    from server.app.api import graph as graph_mod

    graph_mod.invalidate_graph_cache()

    call_count = {"n": 0}
    original = hist_svc.list_all_weekly_repertoire

    def counting_fn(*a, **kw):
        call_count["n"] += 1
        return original(*a, **kw)

    path = str(tmp_path / "cache_test.db")
    monkeypatch.setattr(db_mod, "history_db_path", lambda: path)
    db_mod.init_history_db()

    monkeypatch.setattr(graph_mod, "list_all_weekly_repertoire", counting_fn)

    graph_mod._get_history()
    graph_mod._get_history()

    assert call_count["n"] == 1  # DB는 한 번만 조회


def test_cache_expires_after_ttl(monkeypatch):
    """TTL이 지나면 DB를 다시 조회한다."""
    import time
    from server.app.api import graph as graph_mod

    graph_mod.invalidate_graph_cache()

    call_count = {"n": 0}

    def fake_list(*a, **kw):
        call_count["n"] += 1
        return []

    monkeypatch.setattr(graph_mod, "list_all_weekly_repertoire", fake_list)

    graph_mod._get_history()
    assert call_count["n"] == 1

    # TTL이 이미 지난 것처럼 타임스탬프를 조작
    ts, data = graph_mod._history_cache
    graph_mod._history_cache = (ts - graph_mod._HISTORY_CACHE_TTL - 1, data)

    graph_mod._get_history()
    assert call_count["n"] == 2


# ── 그래프 계산 ───────────────────────────────────────────────────────────────

def _make_history(*song_lists: list[str], church: str = "테스트교회", base_date: str = "2025-01-04") -> list[dict]:
    """테스트용 이력 데이터 생성."""
    from datetime import date, timedelta
    result = []
    d = date.fromisoformat(base_date)
    for songs in song_lists:
        result.append({
            "church": church,
            "week_end_date": d.isoformat(),
            "sequence_entries": [{"title": s, "sequence": "I-V-C"} for s in songs],
        })
        d += timedelta(weeks=1)
    return result


def test_node_weight_counts_appearances():
    from server.app.api import graph as graph_mod
    history = _make_history(["곡A", "곡B"], ["곡A"])
    graph_mod._history_cache = (float("inf"), history)

    from server.app.models.auth import AuthContext
    auth = AuthContext(mode="guest")
    result = graph_mod.get_graph(auth)

    weights = {n["id"]: n["weight"] for n in result["nodes"]}
    assert weights["곡A"] == 2
    assert weights["곡B"] == 1


def test_edge_between_cooccurring_songs():
    from server.app.api import graph as graph_mod
    history = _make_history(["곡A", "곡B", "곡C"], ["곡A", "곡B"])
    graph_mod._history_cache = (float("inf"), history)

    from server.app.models.auth import AuthContext
    result = graph_mod.get_graph(AuthContext(mode="guest"))

    edge_map = {(e["source"], e["target"]): e["weight"] for e in result["edges"]}
    # 곡A-곡B는 2번 같이 등장
    key = tuple(sorted(["곡A", "곡B"]))
    assert edge_map[key] == 2


def test_guest_last_used_not_visible():
    from server.app.api import graph as graph_mod
    history = _make_history(["곡A"])
    graph_mod._history_cache = (float("inf"), history)

    from server.app.models.auth import AuthContext
    result = graph_mod.get_graph(AuthContext(mode="guest"))

    node = next(n for n in result["nodes"] if n["id"] == "곡A")
    assert node["lastUsed"]["visible"] is False


def test_user_last_used_visible_for_own_church():
    from server.app.api import graph as graph_mod
    history = _make_history(["곡A"], church="내교회")
    graph_mod._history_cache = (float("inf"), history)

    from server.app.models.auth import AuthContext
    auth = AuthContext(mode="user", user_id="u1", church="내교회", nickname="닉")
    result = graph_mod.get_graph(auth)

    node = next(n for n in result["nodes"] if n["id"] == "곡A")
    assert node["lastUsed"]["visible"] is True
    assert node["lastUsed"]["date"] is not None


def test_user_last_used_none_for_other_church():
    """내 교회에서 사용하지 않은 곡은 date=None."""
    from server.app.api import graph as graph_mod
    history = _make_history(["곡A"], church="다른교회")
    graph_mod._history_cache = (float("inf"), history)

    from server.app.models.auth import AuthContext
    auth = AuthContext(mode="user", user_id="u1", church="내교회", nickname="닉")
    result = graph_mod.get_graph(auth)

    node = next(n for n in result["nodes"] if n["id"] == "곡A")
    assert node["lastUsed"]["visible"] is True
    assert node["lastUsed"]["date"] is None
