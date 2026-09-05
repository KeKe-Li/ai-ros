"""操作技能：抓取（Grasp）与放置（Place）。"""

from __future__ import annotations

from typing import Mapping

from robot_agent.backends.base import RobotBackend
from robot_agent.core.types import SkillResult
from robot_agent.skills.base import Skill
from robot_agent.world.state import WorldState


class GraspSkill(Skill):
    """抓取可抓取物体（object_id）。"""

    name = "grasp"
    required_params = ("object_id",)

    def preconditions(self, world: WorldState, params: Mapping[str, object]) -> bool:
        obj = world.get(str(params["object_id"]))
        return obj is not None and obj.is_graspable and world.holding is None

    def execute(
        self,
        backend: RobotBackend,
        world: WorldState,
        params: Mapping[str, object],
    ) -> tuple[SkillResult, WorldState]:
        return backend.grasp(world, str(params["object_id"]))

    def postconditions(self, world: WorldState, params: Mapping[str, object]) -> bool:
        return world.holding == str(params["object_id"])


class PlaceSkill(Skill):
    """把当前持有物放入容器（container_id）。"""

    name = "place"
    required_params = ("container_id",)

    def preconditions(self, world: WorldState, params: Mapping[str, object]) -> bool:
        container = world.get(str(params["container_id"]))
        return world.holding is not None and container is not None and container.is_container

    def execute(
        self,
        backend: RobotBackend,
        world: WorldState,
        params: Mapping[str, object],
    ) -> tuple[SkillResult, WorldState]:
        return backend.place(world, str(params["container_id"]))

    def postconditions(self, world: WorldState, params: Mapping[str, object]) -> bool:
        # 放置后机械臂应已释放，且目标容器内至少有一个物体
        container_id = str(params["container_id"])
        return world.holding is None and bool(
            world.find_objects(in_container=container_id)
        )
