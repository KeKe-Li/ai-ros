"""技能管理器（SkillManager）。

负责技能的注册、发现与统一调用。调用前完成参数与前置条件校验：
    - 未注册技能：抛 UnknownSkillError（属于规划/编程错误，需尽早暴露）。
    - 缺少必需参数或前置条件不满足：返回失败 SkillResult（属于运行期状况，
      交由监控器决定重试/重规划），世界保持不变。
"""

from __future__ import annotations

from typing import Mapping

from robot_agent.backends.base import RobotBackend
from robot_agent.core.errors import UnknownSkillError
from robot_agent.core.types import SkillResult
from robot_agent.skills.base import Skill
from robot_agent.world.state import WorldState


class SkillManager:
    """技能注册表与统一调用入口。"""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """注册技能，重名视为配置错误。"""
        if not skill.name:
            raise ValueError("技能必须具备非空 name")
        if skill.name in self._skills:
            raise ValueError(f"技能重复注册：{skill.name}")
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        """按名获取技能，未注册抛 UnknownSkillError。"""
        try:
            return self._skills[name]
        except KeyError as exc:
            raise UnknownSkillError(f"未注册的技能：{name}") from exc

    def names(self) -> list[str]:
        """列出全部已注册技能名（排序，便于展示与发现）。"""
        return sorted(self._skills)

    def invoke(
        self,
        name: str,
        backend: RobotBackend,
        world: WorldState,
        params: Mapping[str, object],
    ) -> tuple[SkillResult, WorldState]:
        """统一调用入口：校验参数与前置条件后执行。"""
        skill = self.get(name)
        missing = [p for p in skill.required_params if p not in params]
        if missing:
            return SkillResult.failure(f"缺少必需参数：{missing}"), world
        if not skill.preconditions(world, params):
            return SkillResult.failure(f"前置条件不满足：{name}"), world
        return skill.execute(backend, world, params)
