"""感知技能：检测当前位置附近匹配条件的物体。

只读技能：不改变世界，检测结果通过 SkillResult.data['object_ids'] 返回。
"""

from __future__ import annotations

from typing import Mapping

from robot_agent.backends.base import RobotBackend
from robot_agent.core.types import SkillResult
from robot_agent.skills.base import Skill
from robot_agent.world.state import WorldState


class DetectObjectSkill(Skill):
    """按 color/graspable 等条件检测物体。"""

    name = "detect"
    required_params = ()

    def execute(
        self,
        backend: RobotBackend,
        world: WorldState,
        params: Mapping[str, object],
    ) -> tuple[SkillResult, WorldState]:
        result = backend.detect(world, params)
        return result, world  # 感知不改变世界

    def postconditions(
        self,
        before: WorldState,
        after: WorldState,
        params: Mapping[str, object],
        result: SkillResult,
    ) -> bool:
        object_ids = result.data.get("object_ids")
        if not isinstance(object_ids, list) or not object_ids:
            return False
        expected = params.get("object_id")
        return expected is None or str(expected) in object_ids
