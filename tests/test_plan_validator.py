"""计划结构、数据引用与目标一致性验证测试。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from robot_agent.core.errors import PlanningError
from robot_agent.planning.base import OutputRef, Plan, SkillCall, ToolCall
from robot_agent.planning.goal import parse_goal
from robot_agent.planning.validator import PlanValidator
from robot_agent.skills import default_skill_manager
from robot_agent.tools.registry import ToolRegistry
from robot_agent.world.grid_world import build_pick_and_place_world

GOAL = "把红色方块放到箱子里"


def _validator(tools: ToolRegistry | None = None):
    return PlanValidator(default_skill_manager(), tools)


def _valid_plan() -> Plan:
    return Plan(
        GOAL,
        (
            SkillCall(
                "detect",
                {"object_id": "red_cube", "graspable": True},
                step_id="detect_object",
            ),
            SkillCall(
                "grasp",
                {
                    "object_id": OutputRef(
                        "detect_object",
                        path=("object_ids", 0),
                        expected="red_cube",
                    )
                },
                depends_on=(0,),
                step_id="grasp_object",
            ),
            SkillCall(
                "navigate",
                {"target_object": "box"},
                depends_on=(1,),
                step_id="navigate_container",
            ),
            SkillCall(
                "place",
                {"container_id": "box"},
                depends_on=(2,),
                step_id="place_object",
            ),
        ),
    )


def test_validator_accepts_goal_aligned_plan_with_output_reference():
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)

    _validator().validate(_valid_plan(), goal, world)


@pytest.mark.parametrize(
    ("plan", "message"),
    [
        (
            Plan(
                GOAL,
                (
                    SkillCall("detect", step_id="same"),
                    SkillCall("detect", step_id="same"),
                ),
            ),
            "重复",
        ),
        (Plan(GOAL, (SkillCall("grasp", step_id="grasp"),)), "缺少必需参数"),
        (Plan(GOAL, (SkillCall("unknown", step_id="unknown"),)), "未注册"),
        (
            Plan(
                GOAL,
                (
                    SkillCall(
                        "grasp",
                        {"object_id": "red_cube"},
                        step_id="grasp",
                    ),
                ),
            ),
            "输出引用",
        ),
        (
            Plan(
                GOAL,
                (
                    SkillCall("detect", step_id="detect"),
                    SkillCall(
                        "grasp",
                        {
                            "object_id": OutputRef(
                                "detect",
                                path=("object_ids", 0),
                                expected="blue_cube",
                            )
                        },
                        depends_on=(0,),
                        step_id="grasp",
                    ),
                ),
            ),
            "目标物体",
        ),
    ],
)
def test_validator_rejects_invalid_skill_plans(plan: Plan, message: str):
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)

    with pytest.raises(PlanningError, match=message):
        _validator().validate(plan, goal, world)


def test_validator_rejects_reference_without_dependency():
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)
    plan = _valid_plan()
    grasp = replace(plan.steps[1], depends_on=())
    plan = replace(plan, steps=(plan.steps[0], grasp, *plan.steps[2:]))

    with pytest.raises(PlanningError, match="依赖"):
        _validator().validate(plan, goal, world)


def test_validator_rejects_plan_for_another_goal():
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)
    plan = replace(_valid_plan(), goal="另一个目标")

    with pytest.raises(PlanningError, match="目标不一致"):
        _validator().validate(plan, goal, world)


def test_validator_rejects_navigation_to_unrelated_entity():
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)
    plan = Plan(
        GOAL,
        (
            SkillCall(
                "navigate",
                {"target_object": "table"},
                step_id="navigate_unrelated",
            ),
        ),
    )

    with pytest.raises(PlanningError, match="导航目标与任务无关"):
        _validator().validate(plan, goal, world)


def test_validator_rejects_unknown_tool():
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)
    plan = Plan(GOAL, (ToolCall("missing", step_id="tool"),))

    with pytest.raises(PlanningError, match="未注册的工具"):
        _validator(ToolRegistry()).validate(plan, goal, world)


def test_validator_allows_empty_plan_only_when_goal_is_satisfied():
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)

    with pytest.raises(PlanningError, match="空计划"):
        _validator().validate(Plan(GOAL), goal, world)

    cube = world.get("red_cube")
    assert cube is not None
    done = world.with_object("red_cube", replace(cube, in_container="box"))
    _validator().validate(Plan(GOAL), goal, done)
