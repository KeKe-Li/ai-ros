"""目标规格（GoalSpec）：确定性的目标达成判定。

将自然语言目标**解析一次**为结构化的成功判据，与规划器（Planner）解耦：
    - 规划器负责"如何做"（把目标分解为技能序列，可能是规则或 LLM）。
    - GoalSpec 负责"是否做完"（对当前世界的纯确定性检查）。

这样目标验证不再依赖 planner.plan()，避免接入 LLMPlanner 后每次验证/重规划都触发
真实模型调用（非确定、慢、耗 token），也避免目标串被反复解析。

解析逻辑集中在此处，供 GoalSpec 与 MockPlanner 复用（DRY）。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from robot_agent.core.errors import PlanningError
from robot_agent.world.state import WorldState

# 颜色关键词映射（中/英）
_COLOR_KEYWORDS: dict[str, str] = {
    "红": "red",
    "红色": "red",
    "red": "red",
    "蓝": "blue",
    "蓝色": "blue",
    "blue": "blue",
    "绿": "green",
    "绿色": "green",
    "green": "green",
}

# 容器关键词（用于确认目标串确实在描述"放入容器"意图）
_CONTAINER_KEYWORDS: tuple[str, ...] = ("箱", "box", "容器", "筐", "篮", "container")


class GoalSpec(ABC):
    """目标达成判据的抽象接口。"""

    @abstractmethod
    def is_satisfied(self, world: WorldState) -> bool:
        """当前世界是否已满足目标（纯确定性检查，无副作用）。"""


@dataclass(frozen=True)
class InContainerGoal(GoalSpec):
    """"把某物放入某容器"类目标。

    object_id/container_id 在解析时结合世界一次性解析定位，之后的判定只做纯查询。
    """

    text: str
    object_id: str
    container_id: str
    color: str | None = None

    def is_satisfied(self, world: WorldState) -> bool:
        obj = world.get(self.object_id)
        return obj is not None and obj.in_container == self.container_id


def parse_goal(text: str, world: WorldState) -> GoalSpec:
    """把目标串结合当前世界解析为 GoalSpec。无法解析时抛 PlanningError。"""
    lowered = text.lower()
    color = _parse_color(lowered)
    container_id = _find_container(lowered, world)
    object_id = _find_target_object(lowered, color, container_id, world)
    return InContainerGoal(
        text=text, object_id=object_id, container_id=container_id, color=color
    )


# --- 解析辅助（模块级，供 parse_goal 与规划器复用）---


def _parse_color(text: str) -> str | None:
    for token, color in _COLOR_KEYWORDS.items():
        if token in text:
            return color
    return None


def _find_container(text: str, world: WorldState) -> str:
    containers = [
        oid for oid, info in sorted(world.objects.items()) if info.is_container
    ]
    if not containers:
        raise PlanningError("世界中不存在可放置的容器")
    explicit = _find_explicit_id(text, containers)
    if explicit is not None:
        return explicit
    if not any(kw in text for kw in _CONTAINER_KEYWORDS):
        raise PlanningError(f"目标未描述有效的容器/放置意图：{text!r}")
    if len(containers) > 1:
        raise PlanningError(f"目标对应多个候选容器，请明确指定：{containers}")
    return containers[0]


def _find_target_object(
    text: str, color: str | None, container_id: str, world: WorldState
) -> str:
    candidates = world.find_objects(color=color, graspable=True)
    # 排除容器自身（理论上容器不可抓取，这里稳妥起见再过滤一次）
    candidates = [c for c in candidates if c != container_id]
    if not candidates:
        raise PlanningError(f"世界中找不到匹配的可抓取物体（color={color}）")
    explicit = _find_explicit_id(text, candidates)
    if explicit is not None:
        return explicit
    if len(candidates) > 1:
        raise PlanningError(f"目标对应多个候选物体，请明确指定：{candidates}")
    return candidates[0]


def _find_explicit_id(text: str, candidates: list[str] | tuple[str, ...]) -> str | None:
    """查找目标文本中最具体的实体 ID；同长度多匹配视为歧义。"""
    matches = [entity_id for entity_id in candidates if entity_id.lower() in text]
    if not matches:
        return None
    longest = max(len(entity_id) for entity_id in matches)
    most_specific = [entity_id for entity_id in matches if len(entity_id) == longest]
    if len(most_specific) > 1:
        raise PlanningError(f"目标同时指定了多个实体：{sorted(most_specific)}")
    return most_specific[0]
