"""世界层测试：WorldState 不可变性、查询与网格仿真器。"""

from __future__ import annotations

import pytest

from robot_agent.core.types import Pose
from robot_agent.world.grid_world import GridWorld, build_pick_and_place_world
from robot_agent.world.state import ObjectInfo, WorldState, build_world


def test_pose_manhattan_distance():
    # Arrange / Act / Assert
    assert Pose(0, 0).manhattan(Pose(3, 4)) == 7


def test_with_robot_pose_returns_new_copy_without_mutating_original():
    # Arrange
    world = build_world(Pose(0, 0), {})

    # Act
    moved = world.with_robot_pose(Pose(2, 3))

    # Assert：原对象不变，新对象已更新
    assert world.robot_pose == Pose(0, 0)
    assert moved.robot_pose == Pose(2, 3)
    assert moved is not world


def test_with_object_does_not_mutate_original_objects():
    # Arrange
    world = build_world(Pose(0, 0), {"a": ObjectInfo(pose=Pose(1, 1))})

    # Act
    updated = world.with_object("b", ObjectInfo(pose=Pose(2, 2), color="red"))

    # Assert
    assert "b" not in world.objects
    assert "b" in updated.objects
    assert updated.get("b").color == "red"


def test_find_objects_filters_by_color_and_graspable():
    # Arrange
    world = build_world(
        Pose(0, 0),
        {
            "red_cube": ObjectInfo(pose=Pose(5, 5), color="red", is_graspable=True),
            "blue_cube": ObjectInfo(pose=Pose(1, 1), color="blue", is_graspable=True),
            "table": ObjectInfo(pose=Pose(5, 5), color=None),
        },
    )

    # Act
    reds = world.find_objects(color="red", graspable=True)

    # Assert
    assert reds == ["red_cube"]


def test_find_objects_filters_by_container():
    # Arrange
    world = build_world(
        Pose(0, 0),
        {"cube": ObjectInfo(pose=Pose(8, 2), is_graspable=True, in_container="box")},
    )

    # Act / Assert
    assert world.find_objects(in_container="box") == ["cube"]
    assert world.find_objects(in_container="drawer") == []


def test_world_state_is_frozen():
    # Arrange
    world = build_world(Pose(0, 0), {})

    # Act / Assert：不可变对象禁止就地修改
    with pytest.raises(Exception):
        world.robot_pose = Pose(1, 1)  # type: ignore[misc]


def test_grid_bounds_and_adjacency():
    # Arrange
    grid = GridWorld(10, 10)

    # Act / Assert
    assert grid.in_bounds(Pose(9, 9))
    assert not grid.in_bounds(Pose(10, 0))
    assert grid.is_adjacent(Pose(5, 5), Pose(5, 6))
    assert not grid.is_adjacent(Pose(5, 5), Pose(5, 7))


def test_failure_injection_budget_is_consumed():
    # Arrange：grasp 前 2 次失败，之后成功
    grid = GridWorld(10, 10, fail_actions={"grasp": 2})

    # Act / Assert
    assert grid.should_fail("grasp") is True
    assert grid.should_fail("grasp") is True
    assert grid.should_fail("grasp") is False
    # 未配置的动作从不失败
    assert grid.should_fail("navigate") is False


def test_build_pick_and_place_world_scene():
    # Arrange / Act
    grid, world = build_pick_and_place_world()

    # Assert
    assert isinstance(world, WorldState)
    assert world.robot_pose == Pose(0, 0)
    assert world.get("red_cube").color == "red"
    assert world.get("box").is_container is True
    assert grid.width == 10 and grid.height == 10
