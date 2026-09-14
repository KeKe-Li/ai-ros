"""规则/mock 任务分解器（默认 Planner）。

面向 pick-and-place 类目标："把 <颜色> <物体> 放到 <容器> 里"。目标解析复用
planning.goal.parse_goal（集中一处，DRY），再结合当前世界生成技能序列。
无需网络与 API key，保证离线可复现。

具备世界感知的**幂等**特性：根据当前世界只产出"剩余步骤"（如已持有物体则跳过
导航/检测/抓取），因此可安全用于异常恢复时的重规划。
"""

from __future__ import annotations

from robot_agent.planning.base import OutputRef, Plan, Planner, SkillCall
from robot_agent.planning.goal import InContainerGoal, parse_goal
from robot_agent.world.state import WorldState


class MockPlanner(Planner):
    """基于规则的确定性分解器。"""

    def plan(self, goal: str, world: WorldState) -> Plan:
        spec = parse_goal(goal, world)
        assert isinstance(spec, InContainerGoal)  # 当前仅支持该目标类型

        # 目标已达成：物体已在容器内
        if spec.is_satisfied(world):
            return Plan(goal=goal, steps=())

        object_id = spec.object_id
        container_id = spec.container_id
        color = spec.color
        steps: list[SkillCall] = []

        # 若尚未持有目标物，则需要 导航->检测->抓取
        if world.holding != object_id:
            target_pose = world.objects[object_id].pose
            if world.robot_pose != target_pose:
                steps.append(
                    _linked(
                        steps,
                        SkillCall(
                            "navigate",
                            {"target_object": object_id},
                            step_id="navigate_object",
                        ),
                    )
                )
            steps.append(
                _linked(
                    steps,
                    SkillCall(
                        "detect",
                        {"object_id": object_id, "color": color, "graspable": True}
                        if color
                        else {"object_id": object_id, "graspable": True},
                        step_id="detect_object",
                    ),
                )
            )
            steps.append(
                _linked(
                    steps,
                    SkillCall(
                        "grasp",
                        {
                            "object_id": OutputRef(
                                "detect_object",
                                path=("object_ids", 0),
                                expected=object_id,
                            )
                        },
                        step_id="grasp_object",
                    ),
                )
            )

        # 导航到容器并放置
        steps.append(
            _linked(
                steps,
                SkillCall(
                    "navigate",
                    {"target_object": container_id},
                    step_id="navigate_container",
                ),
            )
        )
        steps.append(
            _linked(
                steps,
                SkillCall(
                    "place",
                    {"container_id": container_id},
                    step_id="place_object",
                ),
            )
        )

        return Plan(goal=goal, steps=tuple(steps))


def _linked(existing: list[SkillCall], call: SkillCall) -> SkillCall:
    """把 call 线性链接到已有步骤末尾：依赖上一步（若存在）。"""
    if not existing:
        return call
    return SkillCall(
        call.skill,
        call.params,
        depends_on=(len(existing) - 1,),
        step_id=call.step_id,
    )
