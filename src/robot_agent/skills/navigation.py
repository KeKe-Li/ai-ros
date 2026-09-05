"""导航技能：移动到某个目标实体所在位置。"""

from __future__ import annotations

from typing import Mapping

from robot_agent.backends.base import RobotBackend
from robot_agent.core.types import SkillResult
from robot_agent.skills.base import Skill
from robot_agent.world.state import WorldState


class NavigateSkill(Skill):
    """导航到目标实体（target_object）相邻位置。"""

    name = "navigate"
    required_params = ("target_object",)

    def preconditions(self, world: WorldState, params: Mapping[str, object]) -> bool:
        return world.get(str(params["target_object"])) is not None

    def execute(
        self,
        backend: RobotBackend,
        world: WorldState,
        params: Mapping[str, object],
    ) -> tuple[SkillResult, WorldState]:
        target_id = str(params["target_object"])
        target = world.objects[target_id].pose
        return backend.navigate_to(world, target)

    def postconditions(self, world: WorldState, params: Mapping[str, object]) -> bool:
        target_id = str(params["target_object"])
        target = world.objects[target_id].pose
        return world.robot_pose == target
