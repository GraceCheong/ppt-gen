"""앱 설정 (기본 템플릿 등) 영속 저장."""
from __future__ import annotations

import json
import os

from server.app.config import ROOT_DIR

_SETTINGS_PATH = os.path.join(ROOT_DIR, "out", "app_settings.json")


def _read() -> dict:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(data: dict) -> None:
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_default_template() -> str | None:
    return _read().get("default_template_id")


def set_default_template(template_id: str | None) -> None:
    data = _read()
    if template_id:
        data["default_template_id"] = template_id
    else:
        data.pop("default_template_id", None)
    _write(data)


def get_scoped_default_template(scope: str) -> str | None:
    return _read().get("scoped_defaults", {}).get(scope)


def set_scoped_default_template(template_id: str | None, scope: str) -> None:
    data = _read()
    scoped = data.setdefault("scoped_defaults", {})
    if template_id:
        scoped[scope] = template_id
    else:
        scoped.pop(scope, None)
    _write(data)
