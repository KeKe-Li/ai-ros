"""ROS2 适配器 stub 行为与技能注册校验测试。"""

from __future__ import annotations

import pytest

from robot_agent.backends.ros2_backend import ROS2Backend
from robot_agent.core.errors import BackendNotAvailableError
from robot_agent.core.types import Pose
from robot_agent.skills.manager import SkillManager
from robot_agent.skills.navigation import NavigateSkill
from robot_agent.world.grid_world import build_pick_and_place_world


def test_ros2_backend_actions_raise_unavailable():
    # Arrange
    backend = ROS2Backend()
    _, world = build_pick_and_place_world()

    # Act / Assert：未接入真实 ROS2 时每个动作都明确报错
    with pytest.raises(BackendNotAvailableError):
        backend.navigate_to(world, Pose(1, 1))
    with pytest.raises(BackendNotAvailableError):
        backend.detect(world, {})
    with pytest.raises(BackendNotAvailableError):
        backend.grasp(world, "red_cube")
    with pytest.raises(BackendNotAvailableError):
        backend.place(world, "box")


def test_register_empty_name_raises():
    # Arrange
    manager = SkillManager()
    skill = NavigateSkill()
    skill.name = ""  # 模拟非法技能

    # Act / Assert
    with pytest.raises(ValueError):
        manager.register(skill)


def test_register_duplicate_name_raises():
    # Arrange
    manager = SkillManager()
    manager.register(NavigateSkill())

    # Act / Assert
    with pytest.raises(ValueError):
        manager.register(NavigateSkill())
