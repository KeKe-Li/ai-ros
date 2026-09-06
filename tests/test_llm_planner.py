"""可选 LLM 分解器测试：离线回退与 JSON 计划解析。"""

from __future__ import annotations

import pytest

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
        '{"skill":"navigate","params":{"target_object":"red_cube"},"depends_on":[]},'
        '{"skill":"grasp","params":{"object_id":"red_cube"},"depends_on":[0]}]}'
    )

    # Act
    plan = LLMPlanner._parse_plan(GOAL, text)

    # Assert
    assert [s.skill for s in plan.steps] == ["navigate", "grasp"]
    assert plan.steps[1].depends_on == (0,)


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
