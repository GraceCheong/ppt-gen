"""그래프 데이터 API — 교회별 lastUsed 포함."""
from __future__ import annotations

import datetime
import time

from fastapi import APIRouter, Depends

from server.app.api.deps import get_optional_auth_context
from server.app.models.auth import AuthContext
from server.app.services.history_service import list_all_weekly_repertoire

router = APIRouter()

_KST = datetime.timezone(datetime.timedelta(hours=9))

# 이력 목록 TTL 캐시 — 이력이 바뀌어도 최대 5분 후 자동 반영
_HISTORY_CACHE_TTL = 300
_history_cache: tuple[float, list] | None = None  # (monotonic_ts, history_list)


def _get_history() -> list:
    global _history_cache
    now = time.monotonic()
    if _history_cache and now - _history_cache[0] < _HISTORY_CACHE_TTL:
        return _history_cache[1]
    data = list_all_weekly_repertoire(year_from=2020)
    _history_cache = (now, data)
    return data


def invalidate_graph_cache() -> None:
    """이력 변경 시 그래프 캐시를 즉시 무효화한다."""
    global _history_cache
    _history_cache = None


def _today_kst() -> datetime.date:
    return datetime.datetime.now(_KST).date()


def _d_label(date_str: str) -> str:
    try:
        last = datetime.date.fromisoformat(date_str)
    except ValueError:
        return ""
    days = (_today_kst() - last).days
    return f"D+{days}" if days >= 0 else f"D{days}"


@router.get("/api/graph")
def get_graph(auth: AuthContext = Depends(get_optional_auth_context)):
    """
    전체 이력 기반으로 노드/엣지를 계산하고,
    로그인 사용자는 교회 기준 마지막 사용일을 포함해 반환한다.
    """
    history = _get_history()

    node_weight: dict[str, int] = {}
    edge_weight: dict[tuple[str, str], int] = {}
    global_last_used: dict[str, str] = {}   # title → 최근 week_end_date (전체)
    church_last_used: dict[str, str] = {}   # title → 최근 week_end_date (해당 교회)

    user_church = auth.church if auth.mode == "user" else None

    for item in history:
        titles = [e["title"] for e in item["sequence_entries"] if e.get("title")]
        date_str = item["week_end_date"]
        item_church = item.get("church", "")

        for t in titles:
            node_weight[t] = node_weight.get(t, 0) + 1
            prev = global_last_used.get(t)
            if not prev or date_str > prev:
                global_last_used[t] = date_str
            if user_church and item_church == user_church:
                prev_c = church_last_used.get(t)
                if not prev_c or date_str > prev_c:
                    church_last_used[t] = date_str

        for i in range(len(titles)):
            for j in range(i + 1, len(titles)):
                key = tuple(sorted([titles[i], titles[j]]))
                edge_weight[key] = edge_weight.get(key, 0) + 1

    nodes = []
    for title, weight in node_weight.items():
        if user_church:
            last_date = church_last_used.get(title)
            if last_date:
                last_used = {
                    "visible": True,
                    "date": last_date,
                    "dLabel": _d_label(last_date),
                }
            else:
                last_used = {"visible": True, "date": None, "dLabel": None}
        else:
            last_used = {"visible": False, "date": None, "dLabel": None}

        nodes.append({"id": title, "weight": weight, "lastUsed": last_used})

    edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in edge_weight.items()
    ]

    return {"nodes": nodes, "edges": edges}
