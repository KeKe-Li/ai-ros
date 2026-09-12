"""技能标准化接口（Skill）。

所有能力（导航/检测/抓取/放置……）统一遵循同一契约，从而可被 SkillManager
以完全一致的方式发现与调用——这是"标准化技能接口"的核心。

契约：
    - name / required_params：元信息，供发现与参数校验。
    - preconditions(world, params)：执行前的世界前置条件，默认恒真。
    - execute(backend, world, params) -> (SkillResult, 新 WorldState)：实际执行。
    - postconditions(before, after, params, result)：结合执行前后世界与结果校验后置条件，
      供监控做闭环判断，默认恒真。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from robot_agent.backends.base import RobotBackend
from robot_agent.core.types import SkillResult
from robot_agent.world.state import WorldState


class Skill(ABC):
    """技能抽象基类。"""

    name: str = ""
    required_params: tuple[str, ...] = ()

    def preconditions(self, world: WorldState, params: Mapping[str, object]) -> bool:
        """执行前置条件，默认恒真，子类可覆盖。"""
        return True

    @abstractmethod
    def execute(
        self,
        backend: RobotBackend,
        world: WorldState,
        params: Mapping[str, object],
    ) -> tuple[SkillResult, WorldState]:
        """执行技能，返回结果与更新后的世界。"""

    def postconditions(
        self,
        before: WorldState,
        after: WorldState,
        params: Mapping[str, object],
        result: SkillResult,
    ) -> bool:
        """执行后置条件，默认恒真，供监控做闭环校验。"""
        return True
