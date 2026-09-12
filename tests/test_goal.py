"""目标判定测试：确定性 GoalSpec 解析、满足判定，以及与规划器的解耦。"""

from __future__ import annotations

from dataclasses import replace

import pytest

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.core.errors import PlanningError
from robot_agent.planning.base import Plan, Planner
from robot_agent.planning.goal import InContainerGoal, parse_goal
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime
from robot_agent.skills import default_skill_manager
from robot_agent.core.types import Pose
from robot_agent.world.grid_world import build_pick_and_place_world
from robot_agent.world.state import ObjectInfo, WorldState, build_world

GOAL = "把红色方块放到箱子里"


def test_parse_goal_resolves_object_and_container():
    # Arrange
    _, world = build_pick_and_place_world()

    # Act
    spec = parse_goal(GOAL, world)

    # Assert
    assert isinstance(spec, InContainerGoal)
    assert spec.object_id == "red_cube"
    assert spec.container_id == "box"
    assert spec.color == "red"


def test_is_satisfied_toggles_with_world():
    # Arrange
    _, world = build_pick_and_place_world()
    spec = parse_goal(GOAL, world)

    # Act / Assert：初始未达成
    assert spec.is_satisfied(world) is False
    # 入箱后达成
    done = world.with_object("red_cube", replace(world.get("red_cube"), in_container="box"))
    assert spec.is_satisfied(done) is True


def test_parse_goal_without_container_raises():
    # Arrange
    _, world = build_pick_and_place_world()

    # Act / Assert
    with pytest.raises(PlanningError):
        parse_goal("捡起红色方块", world)


def test_parse_goal_recognized_but_absent_color_raises():
    # Arrange：蓝色可识别但世界中不存在
    _, world = build_pick_and_place_world()

    # Act / Assert
    with pytest.raises(PlanningError):
        parse_goal("把蓝色方块放到箱子里", world)


def test_parse_goal_prefers_explicit_entity_ids():
    world = build_world(
        Pose(0, 0),
        {
            "blue_cube": ObjectInfo(Pose(1, 1), color="blue", is_graspable=True),
            "red_cube": ObjectInfo(Pose(2, 2), color="red", is_graspable=True),
            "a_box": ObjectInfo(Pose(3, 3), is_container=True),
            "z_box": ObjectInfo(Pose(4, 4), is_container=True),
        },
    )

    spec = parse_goal("把 red_cube 放到 z_box 里", world)

    assert isinstance(spec, InContainerGoal)
    assert spec.object_id == "red_cube"
    assert spec.container_id == "z_box"


def test_parse_goal_rejects_ambiguous_containers():
    world = build_world(
        Pose(0, 0),
        {
            "red_cube": ObjectInfo(Pose(1, 1), color="red", is_graspable=True),
            "left_box": ObjectInfo(Pose(2, 2), is_container=True),
            "right_box": ObjectInfo(Pose(3, 3), is_container=True),
        },
    )

    with pytest.raises(PlanningError, match="多个.*容器"):
        parse_goal("把红色方块放到箱子里", world)


def test_parse_goal_rejects_ambiguous_objects():
    world = build_world(
        Pose(0, 0),
        {
            "red_cube_1": ObjectInfo(Pose(1, 1), color="red", is_graspable=True),
            "red_cube_2": ObjectInfo(Pose(2, 2), color="red", is_graspable=True),
            "box": ObjectInfo(Pose(3, 3), is_container=True),
        },
    )

    with pytest.raises(PlanningError, match="多个.*物体"):
        parse_goal("把红色方块放到箱子里", world)


class _CountingPlanner(Planner):
    """包装 MockPlanner 并统计 plan() 调用次数，用于验证解耦。"""

    def __init__(self) -> None:
        self._inner = MockPlanner()
        self.calls = 0

    def plan(self, goal: str, world: WorldState) -> Plan:
        self.calls += 1
        return self._inner.plan(goal, world)


def test_goal_verification_does_not_invoke_planner():
    # Arrange：顺利路径，无失败、无重规划
    grid, world = build_pick_and_place_world()
    planner = _CountingPlanner()
    runtime = AgentRuntime(SimBackend(grid), default_skill_manager(), planner)

    # Act
    report = runtime.run(GOAL, world)

    # Assert：成功，且 planner 仅被用于"分解"一次；目标验证未再触发 plan()
    assert report.succeeded
    assert planner.calls == 1
