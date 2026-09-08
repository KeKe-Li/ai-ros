"""监控与异常恢复测试：重试成功、不可恢复失败、目标校验。"""

from __future__ import annotations

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.core.task import TaskStatus
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime
from robot_agent.runtime.monitor import ExecutionMonitor
from robot_agent.skills import default_skill_manager
from robot_agent.world.grid_world import build_pick_and_place_world

GOAL = "把红色方块放到箱子里"


def _runtime(fail_actions=None, **kw):
    grid, world = build_pick_and_place_world(fail_actions=fail_actions)
    runtime = AgentRuntime(
        SimBackend(grid), default_skill_manager(), MockPlanner(), **kw
    )
    return runtime, world


def test_verify_goal_uses_planner_idempotency():
    # Arrange
    _, world = build_pick_and_place_world()
    from dataclasses import replace

    world = world.with_object("red_cube", replace(world.get("red_cube"), in_container="box"))

    # Act / Assert
    assert ExecutionMonitor().verify_goal(MockPlanner(), GOAL, world) is True


def test_transient_grasp_failure_recovers_via_retry():
    # Arrange：grasp 首次失败，重试上限 2
    runtime, world = _runtime(fail_actions={"grasp": 1}, max_retries=2)

    # Act
    report = runtime.run(GOAL, world)

    # Assert：最终成功，且轨迹中既有失败的 grasp 也有成功的 grasp
    assert report.succeeded
    assert report.world.get("red_cube").in_container == "box"
    grasp_records = [r for r in report.trace if r.skill == "grasp"]
    assert any(r.status == "failed" for r in grasp_records)
    assert any(r.status == "ok" for r in grasp_records)


def test_happy_path_no_failures_succeeds_without_replan():
    # Arrange
    runtime, world = _runtime()

    # Act
    report = runtime.run(GOAL, world)

    # Assert
    assert report.succeeded
    assert report.replans == 0
    assert [r.skill for r in report.trace] == [
        "navigate",
        "detect",
        "grasp",
        "navigate",
        "place",
    ]


def test_unrecoverable_failure_marks_task_failed():
    # Arrange：grasp 持续失败，重试与重规划均无法恢复
    runtime, world = _runtime(
        fail_actions={"grasp": 100}, max_retries=1, max_replans=1
    )

    # Act
    report = runtime.run(GOAL, world)

    # Assert
    assert not report.succeeded
    assert report.task.status is TaskStatus.FAILED
    assert report.task.error


def test_replan_is_attempted_before_giving_up():
    # Arrange
    runtime, world = _runtime(
        fail_actions={"grasp": 100}, max_retries=0, max_replans=2
    )

    # Act
    report = runtime.run(GOAL, world)

    # Assert：达到重规划上限
    assert report.replans == 2
    assert report.task.status is TaskStatus.FAILED
