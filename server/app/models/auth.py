from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class AuthContext:
    mode: Literal["guest", "user"]
    user_id: Optional[str] = None
    church: Optional[str] = None
    nickname: Optional[str] = None
