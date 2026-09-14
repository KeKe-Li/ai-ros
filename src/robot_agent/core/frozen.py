"""递归不可变快照与 JSON-safe 编码辅助。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any


def freeze_value(value: Any) -> Any:
    """递归复制并冻结常见容器，切断调用方持有的可变引用。"""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze_value(item) for item in value)
    return value


def freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen = freeze_value(value)
    assert isinstance(frozen, Mapping)
    return frozen


def to_jsonable(value: Any) -> Any:
    """把冻结容器、枚举和 dataclass 转为 JSON 可编码结构。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: to_jsonable(getattr(value, item.name)) for item in fields(value)
        }
    raise TypeError(f"不支持 JSON 编码的类型：{type(value).__name__}")
