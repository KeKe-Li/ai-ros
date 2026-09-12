"""可选 LLM 分解器测试：离线回退与 JSON 计划解析。"""

from __future__ import annotations

import pytest

from robot_agent.planning.base import OutputRef, ToolCall
from robot_agent.planning.llm_planner import LLMPlanner
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.world.grid_world import build_pick_and_place_world

GOAL = "把红色方块放到箱子里"


def test_offline_falls_back_to_mock_planner():
    # Arrange：无 anthropic/无密钥环境
    _, world = build_pick_and_place_world()
    planner = LLMPlanner()

    # Act
    plan = planner.plan(GOAL, world)

    # Assert：回退到规则分解，结果与 MockPlanner 一致
    assert planner.last_source == "fallback"
    expected = MockPlanner().plan(GOAL, world)
    assert [s.skill for s in plan.steps] == [s.skill for s in expected.steps]


def test_parse_plan_from_valid_json():
    # Arrange
    text = (
        '这是计划：{"steps":['
        '{"id":"navigate_object","skill":"navigate",'
        '"params":{"target_object":"red_cube"},"depends_on":[]},'
        '{"id":"grasp_object","skill":"grasp",'
        '"params":{"object_id":{"$ref":{"step_id":"detect_object",'
        '"path":["object_ids",0],"expected":"red_cube"}}},'
        '"depends_on":[0]}]}'
    )

    # Act
    plan = LLMPlanner._parse_plan(GOAL, text)

    # Assert
    assert [s.skill for s in plan.steps] == ["navigate", "grasp"]
    assert plan.steps[1].depends_on == (0,)
    assert plan.steps[0].step_id == "navigate_object"
    assert plan.steps[1].params["object_id"] == OutputRef(
        "detect_object", path=("object_ids", 0), expected="red_cube"
    )


def test_parse_plan_supports_registered_tool_call():
    text = (
        '{"steps":[{"id":"locate","tool":"locate_object",'
        '"params":{"object_id":"red_cube"},"depends_on":[]}]}'
    )

    plan = LLMPlanner._parse_plan(GOAL, text)

    assert isinstance(plan.steps[0], ToolCall)
    assert plan.steps[0].tool == "locate_object"
    assert plan.steps[0].step_id == "locate"


def test_parse_plan_rejects_unknown_tool():
    text = '{"steps":[{"id":"unsafe","tool":"shell","params":{}}]}'

    with pytest.raises(ValueError, match="未知工具"):
        LLMPlanner._parse_plan(GOAL, text)


def test_parse_plan_preserves_non_string_expected_value():
    text = (
        '{"steps":[{"id":"locate","tool":"count_objects","params":{}},'
        '{"id":"use_count","tool":"count_objects","params":{"color":'
        '{"$ref":{"step_id":"locate","path":["value"],"expected":3}}},'
        '"depends_on":[0]}]}'
    )

    plan = LLMPlanner._parse_plan(GOAL, text)

    reference = plan.steps[1].params["color"]
    assert isinstance(reference, OutputRef)
    assert reference.expected == 3


def test_parse_plan_rejects_unknown_skill():
    # Arrange
    text = '{"steps":[{"skill":"fly","params":{}}]}'

    # Act / Assert
    with pytest.raises(ValueError):
        LLMPlanner._parse_plan(GOAL, text)


def test_parse_plan_rejects_non_json():
    # Act / Assert
    with pytest.raises(ValueError):
        LLMPlanner._parse_plan(GOAL, "抱歉我不知道")
