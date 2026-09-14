"""公共数据类型与枚举。

统一技能调用的结果契约（SkillResult）与世界坐标（Pose）。所有数据模型均为
不可变（frozen dataclass），更新语义通过返回新副本实现，避免隐藏副作用。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from robot_agent.core.frozen import freeze_mapping


class SkillStatus(StrEnum):
    """技能执行状态。"""

    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


@dataclass(frozen=True)
class SkillResult:
    """技能执行结果的统一返回契约。

    data 用于携带结构化输出（如检测到的物体 id 列表）。
    """

    status: SkillStatus
    message: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", freeze_mapping(self.data))

    @property
    def ok(self) -> bool:
        """是否执行成功。"""
        return self.status is SkillStatus.SUCCESS

    @classmethod
    def success(cls, message: str = "", **data: Any) -> SkillResult:
        """构造成功结果的便捷方法。"""
        return cls(SkillStatus.SUCCESS, message, dict(data))

    @classmethod
    def failure(cls, message: str = "", **data: Any) -> SkillResult:
        """构造失败结果的便捷方法。"""
        return cls(SkillStatus.FAILURE, message, dict(data))


@dataclass(frozen=True)
class Pose:
    """网格世界中的离散坐标。"""

    x: int
    y: int

    def manhattan(self, other: Pose) -> int:
        """到另一位姿的曼哈顿距离，用于路径步数估算。"""
        return abs(self.x - other.x) + abs(self.y - other.y)
