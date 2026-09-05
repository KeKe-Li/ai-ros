"""机器人执行层抽象接口（RobotBackend）。

这是"上层智能"与"底层执行"的解耦边界（依赖倒置）：技能只依赖本抽象，
默认由 SimBackend（纯 Python 仿真）实现，部署到 Linux 时可替换为 ROS2Backend，
上层代码无需改动。

约定：会改变世界的动作返回 (SkillResult, 新 WorldState)；只读动作（detect）
仅返回 SkillResult。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from robot_agent.core.types import Pose, SkillResult
from robot_agent.world.state import WorldState


class RobotBackend(ABC):
    """机器人底层能力的统一抽象。"""

    @abstractmethod
    def navigate_to(
        self, world: WorldState, target: Pose
    ) -> tuple[SkillResult, WorldState]:
        """导航到目标位姿。"""

    @abstractmethod
    def detect(self, world: WorldState, query: Mapping[str, object]) -> SkillResult:
        """在当前位置感知匹配 query 的物体，结果置于 data['object_ids']。"""

    @abstractmethod
    def grasp(self, world: WorldState, object_id: str) -> tuple[SkillResult, WorldState]:
        """抓取指定物体。"""

    @abstractmethod
    def place(
        self, world: WorldState, container_id: str
    ) -> tuple[SkillResult, WorldState]:
        """将当前持有物放入指定容器。"""
