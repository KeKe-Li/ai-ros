"""记忆（Memory）：短期与长期。

    - 短期：本次执行（episode）的事件流，供追溯与上下文回顾。
    - 长期：键值对，可选持久化到 JSON 文件，跨会话保留经验。

Memory 是有状态的累加装置（非流经业务逻辑的数据模型），episode 内部可变，
对外 episode()/recent() 返回副本以避免外部误改。
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from robot_agent.core.errors import MemoryCorruptionError
from robot_agent.core.frozen import freeze_mapping, to_jsonable


@dataclass(frozen=True)
class MemoryEvent:
    """一条短期记忆事件。"""

    kind: str
    fields: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", freeze_mapping(self.fields))


class Memory:
    """短期 + 长期记忆存储。

    Args:
        store_path: 长期记忆的 JSON 文件路径；为 None 时长期记忆仅驻留内存。
    """

    def __init__(self, store_path: str | Path | None = None) -> None:
        self._episode: list[MemoryEvent] = []
        self._store_path = Path(store_path) if store_path else None
        self._long_term: dict[str, Any] = {}
        if self._store_path and self._store_path.exists():
            try:
                loaded = json.loads(self._store_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise MemoryCorruptionError(
                    f"长期记忆文件损坏：{self._store_path}"
                ) from exc
            if not isinstance(loaded, dict):
                raise MemoryCorruptionError("长期记忆文件根结构必须是 JSON 对象")
            self._long_term = loaded

    # --- 短期记忆 ---

    def record(self, kind: str, **fields: Any) -> None:
        """追加一条短期事件。"""
        self._episode.append(MemoryEvent(kind, dict(fields)))

    def episode(self) -> list[MemoryEvent]:
        """返回本次 episode 的全部事件（副本）。"""
        return list(self._episode)

    def recent(self, n: int) -> list[MemoryEvent]:
        """返回最近 n 条事件（副本）。"""
        if n <= 0:
            return []
        return list(self._episode[-n:])

    def clear_episode(self) -> None:
        """清空短期记忆，开始新 episode。"""
        self._episode = []

    # --- 长期记忆 ---

    def store(self, key: str, value: Any) -> None:
        """写入长期记忆，若配置了路径则持久化。"""
        candidate = dict(self._long_term)
        candidate[key] = to_jsonable(value)
        encoded = json.dumps(candidate, ensure_ascii=False, indent=2)
        self._flush(encoded)
        self._long_term = candidate

    def recall(self, key: str, default: Any = None) -> Any:
        """读取长期记忆。"""
        return self._long_term.get(key, default)

    def _flush(self, encoded: str) -> None:
        if self._store_path is not None:
            self._store_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=self._store_path.parent,
                    prefix=f".{self._store_path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                    temporary_path = Path(handle.name)
                os.replace(temporary_path, self._store_path)
            finally:
                if temporary_path is not None and temporary_path.exists():
                    temporary_path.unlink()
