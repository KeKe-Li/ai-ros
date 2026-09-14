"""统一技能/工具能力契约测试。"""

from __future__ import annotations

import pytest

from robot_agent.core.capabilities import (
    CapabilityKind,
    CapabilitySpec,
    ParameterSpec,
    SideEffect,
)
from robot_agent.core.errors import PlanningError
from robot_agent.planning.base import Plan, ToolCall
from robot_agent.planning.goal import parse_goal
from robot_agent.planning.llm_planner import LLMPlanner
from robot_agent.planning.validator import PlanValidator
from robot_agent.skills import default_skill_manager
from robot_agent.tools import default_tool_registry
from robot_agent.world.grid_world import build_pick_and_place_world

GOAL = "把红色方块放到箱子里"


def test_default_registries_expose_capability_specs():
    skills = default_skill_manager()
    tools = default_tool_registry()

    assert skills.spec("grasp").parameters["object_id"].accepted_types == (str,)
    assert tools.spec("locate_object").parameters["object_id"].required
    assert tools.spec("locate_object").outputs["value"].accepted_types


@pytest.mark.parametrize("params", [{}, {"object_id": 123}])
def test_plan_validator_rejects_missing_or_wrong_tool_parameters(params):
    _, world = build_pick_and_place_world()
    goal = parse_goal(GOAL, world)
    tools = default_tool_registry()
    plan = Plan(GOAL, (ToolCall("locate_object", params, step_id="locate"),))

    with pytest.raises(PlanningError, match="参数"):
        PlanValidator(default_skill_manager(), tools).validate(plan, goal, world)


def test_llm_parser_uses_supplied_capability_catalog():
    custom = CapabilitySpec(
        name="inspect_battery",
        kind=CapabilityKind.TOOL,
        description="读取电量",
        parameters={},
        outputs={"value": ParameterSpec((int,), required=True)},
        side_effect=SideEffect.NONE,
    )
    text = '{"steps":[{"id":"battery","tool":"inspect_battery","params":{}}]}'

    plan = LLMPlanner._parse_plan(GOAL, text, capabilities=(custom,))

    assert plan.steps[0].tool == "inspect_battery"


def test_capability_spec_rejects_unknown_parameter():
    spec = default_tool_registry().spec("count_objects")

    with pytest.raises(ValueError, match="未知参数"):
        spec.validate_params({"unexpected": True})


def test_capability_spec_defensively_freezes_contract_mappings():
    parameters = {"level": ParameterSpec((int,), required=True)}
    spec = CapabilitySpec(
        name="set_level",
        kind=CapabilityKind.SKILL,
        description="设置等级",
        parameters=parameters,
    )

    parameters.clear()

    assert "level" in spec.parameters
    with pytest.raises(TypeError):
        spec.parameters["other"] = ParameterSpec((str,))
