"""根据完整实体 ID 和别名解析自然语言中的世界实体。"""

from __future__ import annotations

import re
from collections.abc import Iterable

from robot_agent.core.errors import PlanningError
from robot_agent.world.state import WorldState

_ASCII_IDENTIFIER = re.compile(r"^[a-z0-9_]+$", re.IGNORECASE)


def contains_token(text: str, token: str) -> bool:
    """判断文本是否包含完整 token，避免 `box` 误命中 `sandbox`。"""
    lowered_text = text.lower()
    lowered_token = token.lower()
    if _ASCII_IDENTIFIER.fullmatch(lowered_token):
        pattern = rf"(?<![a-z0-9_]){re.escape(lowered_token)}(?![a-z0-9_])"
        return re.search(pattern, lowered_text, re.IGNORECASE) is not None
    return lowered_token in lowered_text


class EntityResolver:
    """在给定候选集合中按完整 ID 或别名解析唯一实体。"""

    def __init__(self, world: WorldState) -> None:
        self._world = world

    def resolve(self, text: str, candidates: Iterable[str], role: str) -> str | None:
        matches: list[str] = []
        for entity_id in candidates:
            info = self._world.get(entity_id)
            aliases = info.aliases if info is not None else ()
            if any(contains_token(text, token) for token in (entity_id, *aliases)):
                matches.append(entity_id)
        if len(matches) > 1:
            raise PlanningError(f"目标同时匹配多个候选{role}：{sorted(matches)}")
        return matches[0] if matches else None
