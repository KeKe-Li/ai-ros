"""规划器接口与计划数据模型。

Planner 把自然语言/任务指令（goal）结合当前世界状态分解为一串技能调用（Plan）。
计划为不可变数据：每个 SkillCall 通过 depends_on 声明对前序步骤的依赖，供调度器排序。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from robot_agent.world.state import WorldState


@dataclass(frozen=True)
class OutputRef:
    """对先前步骤结构化输出的引用。"""

    step_id: str
    path: tuple[str | int, ...]
    expected: object | None = None


@dataclass(frozen=True)
class SkillCall:
    """一次技能调用：技能名 + 参数 + 依赖的前序步骤下标。"""

    skill: str
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[int, ...] = ()
    step_id: str = ""


@dataclass(frozen=True)
class ToolCall:
    """一次只读工具调用；工具不会改变世界状态。"""

    tool: str
    params: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[int, ...] = ()
    step_id: str = ""


PlanStep: TypeAlias = SkillCall | ToolCall


@dataclass(frozen=True)
class Plan:
    """由若干技能调用构成的计划。"""

    goal: str
    steps: tuple[PlanStep, ...] = ()

    @property
    def is_empty(self) -> bool:
        """空计划表示目标已满足、无需动作。"""
        return len(self.steps) == 0


class Planner(ABC):
    """任务理解与分解的统一接口。"""

    @abstractmethod
    def plan(self, goal: str, world: WorldState) -> Plan:
        """将目标结合当前世界分解为计划。"""
