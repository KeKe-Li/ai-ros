"""工具调用测试：注册表与内置信息工具。"""

from __future__ import annotations

import pytest

from robot_agent.core.types import Pose
from robot_agent.tools.registry import default_tool_registry
from robot_agent.world.grid_world import build_pick_and_place_world


def test_registry_lists_builtin_tools():
    # Arrange / Act
    registry = default_tool_registry()

    # Assert
    assert set(registry.names()) == {
        "locate_object",
        "count_objects",
        "estimate_path_cost",
    }
    assert "查询物体坐标" in registry.describe()["locate_object"]


def test_locate_object_tool():
    # Arrange
    registry = default_tool_registry()
    _, world = build_pick_and_place_world()

    # Act / Assert
    assert registry.call("locate_object", world, "red_cube") == Pose(5, 5)
    assert registry.call("locate_object", world, "ghost") is None


def test_count_and_path_cost_tools():
    # Arrange
    registry = default_tool_registry()
    _, world = build_pick_and_place_world()

    # Act / Assert
    assert registry.call("count_objects", world) == 3
    assert registry.call("count_objects", world, color="red") == 1
    # 机器人 (0,0) 到桌子 (5,5) 的曼哈顿步数
    assert registry.call("estimate_path_cost", world, "table") == 10


def test_unknown_tool_raises():
    # Arrange
    registry = default_tool_registry()

    # Act / Assert
    with pytest.raises(KeyError):
        registry.call("teleport")


def test_duplicate_registration_raises():
    # Arrange
    registry = default_tool_registry()

    # Act / Assert
    with pytest.raises(ValueError):
        registry.register("locate_object", "dup", lambda: None)
