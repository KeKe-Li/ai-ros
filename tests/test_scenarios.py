"""内置场景装载测试。"""

from __future__ import annotations

import pytest

from robot_agent.scenarios import (
    build_world_from_scenario,
    list_scenarios,
    load_scenario,
)


def test_list_scenarios_returns_known_specs():
    specs = list_scenarios()
    names = [spec.name for spec in specs]
    assert "pick_and_place_basic" in names
    assert "pick_and_place_retry_once" in names
    assert "already_satisfied" in names
    assert "ambiguous_red_cube" in names


def test_load_known_scenario():
    spec = load_scenario("pick_and_place_basic")
    assert spec.goal == "把红色方块放到箱子里"
    assert spec.width == 10
    assert spec.height == 10


def test_load_unknown_scenario_raises():
    with pytest.raises(ValueError, match="未知场景"):
        load_scenario("not_exist")


def test_build_world_from_scenario():
    spec = load_scenario("pick_and_place_basic")
    grid, world = build_world_from_scenario(spec)

    assert grid.width == 10
    assert grid.height == 10
    assert world.robot_pose.x == 0
    assert world.robot_pose.y == 0
    assert world.get("red_cube") is not None
    assert world.get("box") is not None


def test_already_satisfied_scenario_keeps_cube_in_box():
    spec = load_scenario("already_satisfied")
    _, world = build_world_from_scenario(spec)

    cube = world.get("red_cube")
    assert cube is not None
    assert cube.in_container == "box"
