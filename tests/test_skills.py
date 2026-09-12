"""技能层与仿真后端测试：动作正确性、前后置条件、失败注入与统一调用。"""

from __future__ import annotations

import pytest

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.core.errors import UnknownSkillError
from robot_agent.core.types import Pose, SkillResult
from robot_agent.skills import default_skill_manager
from robot_agent.skills.manipulation import PlaceSkill
from robot_agent.world.grid_world import GridWorld, build_pick_and_place_world
from robot_agent.world.state import ObjectInfo, build_world


def _sim_and_world(fail_actions=None):
    grid, world = build_pick_and_place_world(fail_actions=fail_actions)
    return SimBackend(grid), world


def test_navigate_moves_robot_to_target():
    # Arrange
    backend, world = _sim_and_world()

    # Act
    result, new_world = backend.navigate_to(world, Pose(5, 5))

    # Assert
    assert result.ok
    assert new_world.robot_pose == Pose(5, 5)
    assert world.robot_pose == Pose(0, 0)  # 原世界不变


def test_navigate_to_out_of_bounds_fails():
    # Arrange
    backend, world = _sim_and_world()

    # Act
    result, new_world = backend.navigate_to(world, Pose(99, 99))

    # Assert
    assert not result.ok
    assert new_world is world


def test_detect_finds_red_cube_only_when_adjacent():
    # Arrange
    backend, world = _sim_and_world()

    # Act：机器人在起点检测不到桌上的方块
    far = backend.detect(world, {"color": "red", "graspable": True})
    # 移动到桌旁后可检测
    _, at_table = backend.navigate_to(world, Pose(5, 5))
    near = backend.detect(at_table, {"color": "red", "graspable": True})

    # Assert
    assert not far.ok
    assert near.ok
    assert near.data["object_ids"] == ["red_cube"]


def test_detect_respects_explicit_object_id_filter():
    backend, world = _sim_and_world()
    _, at_table = backend.navigate_to(world, Pose(5, 5))

    result = backend.detect(at_table, {"object_id": "missing", "graspable": True})

    assert not result.ok
    assert result.data["object_ids"] == []


def test_grasp_requires_adjacency():
    # Arrange
    backend, world = _sim_and_world()

    # Act：起点抓取失败（不相邻）
    result, _ = backend.grasp(world, "red_cube")

    # Assert
    assert not result.ok


def test_grasp_success_updates_holding():
    # Arrange
    backend, world = _sim_and_world()
    _, at_table = backend.navigate_to(world, Pose(5, 5))

    # Act
    result, grasped = backend.grasp(at_table, "red_cube")

    # Assert
    assert result.ok
    assert grasped.holding == "red_cube"


def test_grasp_non_graspable_fails():
    # Arrange
    backend, world = _sim_and_world()
    _, at_table = backend.navigate_to(world, Pose(5, 5))

    # Act：桌子不可抓取
    result, _ = backend.grasp(at_table, "table")

    # Assert
    assert not result.ok


def test_place_puts_object_into_container():
    # Arrange
    backend, world = _sim_and_world()
    _, at_table = backend.navigate_to(world, Pose(5, 5))
    _, grasped = backend.grasp(at_table, "red_cube")
    _, at_box = backend.navigate_to(grasped, Pose(8, 2))

    # Act
    result, done = backend.place(at_box, "box")

    # Assert
    assert result.ok
    assert done.holding is None
    assert done.get("red_cube").in_container == "box"


def test_place_without_holding_fails():
    # Arrange
    backend, world = _sim_and_world()
    _, at_box = backend.navigate_to(world, Pose(8, 2))

    # Act
    result, _ = backend.place(at_box, "box")

    # Assert
    assert not result.ok


def test_place_postcondition_requires_held_object_to_enter_target_container():
    before = build_world(
        Pose(0, 0),
        {
            "old_cube": ObjectInfo(
                Pose(1, 1), is_graspable=True, in_container="box"
            ),
            "target_cube": ObjectInfo(Pose(0, 0), is_graspable=True),
            "box": ObjectInfo(Pose(1, 1), is_container=True),
        },
    ).with_holding("target_cube")
    # 模拟错误后端：释放机械臂，但没有把本次持有物放入容器。
    after = before.with_holding(None)

    passed = PlaceSkill().postconditions(
        before,
        after,
        {"container_id": "box"},
        SkillResult.success("后端误报成功"),
    )

    assert passed is False


def test_place_postcondition_accepts_correctly_placed_held_object():
    backend, world = _sim_and_world()
    _, at_table = backend.navigate_to(world, Pose(5, 5))
    _, before = backend.grasp(at_table, "red_cube")
    _, before = backend.navigate_to(before, Pose(8, 2))
    result, after = backend.place(before, "box")

    passed = PlaceSkill().postconditions(
        before, after, {"container_id": "box"}, result
    )

    assert passed is True


def test_failure_injection_makes_grasp_fail_once():
    # Arrange：注入 grasp 失败 1 次
    backend, world = _sim_and_world(fail_actions={"grasp": 1})
    _, at_table = backend.navigate_to(world, Pose(5, 5))

    # Act
    first, _ = backend.grasp(at_table, "red_cube")
    second, grasped = backend.grasp(at_table, "red_cube")

    # Assert：首次失败，重试成功
    assert not first.ok
    assert second.ok and grasped.holding == "red_cube"


def test_manager_unknown_skill_raises():
    # Arrange
    backend, world = _sim_and_world()
    manager = default_skill_manager()

    # Act / Assert
    with pytest.raises(UnknownSkillError):
        manager.invoke("fly", backend, world, {})


def test_manager_missing_param_returns_failure():
    # Arrange
    backend, world = _sim_and_world()
    manager = default_skill_manager()

    # Act：grasp 缺少 object_id
    result, new_world = manager.invoke("grasp", backend, world, {})

    # Assert
    assert not result.ok
    assert "缺少必需参数" in result.message
    assert new_world is world


def test_manager_precondition_failure_returns_failure():
    # Arrange
    backend, world = _sim_and_world()
    manager = default_skill_manager()

    # Act：起点未持有物体，place 前置条件不满足
    result, _ = manager.invoke("place", backend, world, {"container_id": "box"})

    # Assert
    assert not result.ok
    assert "前置条件不满足" in result.message


def test_full_skill_sequence_reaches_goal_via_manager():
    # Arrange
    grid, world = build_pick_and_place_world()
    backend = SimBackend(grid)
    manager = default_skill_manager()

    # Act：导航->检测->抓取->导航->放置
    _, world = manager.invoke("navigate", backend, world, {"target_object": "table"})
    detect_result, world = manager.invoke(
        "detect", backend, world, {"color": "red", "graspable": True}
    )
    _, world = manager.invoke("grasp", backend, world, {"object_id": "red_cube"})
    _, world = manager.invoke("navigate", backend, world, {"target_object": "box"})
    place_result, world = manager.invoke(
        "place", backend, world, {"container_id": "box"}
    )

    # Assert：闭环达成
    assert detect_result.data["object_ids"] == ["red_cube"]
    assert place_result.ok
    assert world.get("red_cube").in_container == "box"
    assert world.holding is None
