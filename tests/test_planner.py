"""规划层测试：MockPlanner 的分解正确性、世界感知与幂等重规划。"""

from __future__ import annotations

import pytest

from robot_agent.core.errors import PlanningError
from robot_agent.planning.base import OutputRef
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.world.grid_world import build_pick_and_place_world


def test_plan_decomposes_full_pick_and_place_sequence():
    # Arrange
    _, world = build_pick_and_place_world()
    planner = MockPlanner()

    # Act
    plan = planner.plan("把红色方块放到箱子里", world)

    # Assert：完整 5 步序列
    assert [s.skill for s in plan.steps] == [
        "navigate",
        "detect",
        "grasp",
        "navigate",
        "place",
    ]
    assert plan.steps[0].params["target_object"] == "red_cube"
    assert plan.steps[-1].params["container_id"] == "box"
    assert [step.step_id for step in plan.steps] == [
        "navigate_object",
        "detect_object",
        "grasp_object",
        "navigate_container",
        "place_object",
    ]
    assert plan.steps[1].params["object_id"] == "red_cube"
    assert plan.steps[2].params["object_id"] == OutputRef(
        "detect_object", path=("object_ids", 0), expected="red_cube"
    )


def test_plan_steps_have_linear_dependencies():
    # Arrange
    _, world = build_pick_and_place_world()

    # Act
    plan = MockPlanner().plan("把红色方块放到箱子里", world)

    # Assert：每步依赖前一步
    assert plan.steps[0].depends_on == ()
    for i in range(1, len(plan.steps)):
        assert plan.steps[i].depends_on == (i - 1,)


def test_replan_when_already_holding_skips_pick_steps():
    # Arrange：机器人已持有方块
    _, world = build_pick_and_place_world()
    world = world.with_holding("red_cube")

    # Act
    plan = MockPlanner().plan("把红色方块放到箱子里", world)

    # Assert：只剩 导航->放置
    assert [s.skill for s in plan.steps] == ["navigate", "place"]


def test_plan_empty_when_goal_already_satisfied():
    # Arrange：方块已在箱子里
    _, world = build_pick_and_place_world()
    cube = world.get("red_cube")
    from dataclasses import replace

    world = world.with_object("red_cube", replace(cube, in_container="box"))

    # Act
    plan = MockPlanner().plan("把红色方块放到箱子里", world)

    # Assert
    assert plan.is_empty


def test_plan_without_container_keyword_raises():
    # Arrange
    _, world = build_pick_and_place_world()

    # Act / Assert
    with pytest.raises(PlanningError):
        MockPlanner().plan("捡起红色方块", world)


def test_plan_with_recognized_but_absent_color_raises():
    # Arrange：蓝色可被识别，但世界中不存在蓝色可抓取物
    _, world = build_pick_and_place_world()

    # Act / Assert
    with pytest.raises(PlanningError):
        MockPlanner().plan("把蓝色方块放到箱子里", world)
