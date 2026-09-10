"""运行时异常健壮性测试：执行期异常被捕获并转为失败走恢复，而非崩溃。"""

from __future__ import annotations

from robot_agent.backends.ros2_backend import ROS2Backend
from robot_agent.backends.sim_backend import SimBackend
from robot_agent.core.task import TaskStatus
from robot_agent.core.types import Pose, SkillResult
from robot_agent.memory.memory import Memory
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime.agent_runtime import AgentRuntime
from robot_agent.skills import default_skill_manager
from robot_agent.world.grid_world import GridWorld, build_pick_and_place_world
from robot_agent.world.state import WorldState

GOAL = "把红色方块放到箱子里"


class _RaisingGraspBackend(SimBackend):
    """在 grasp 上抛异常若干次，其余委托父类，模拟机械臂驱动故障。"""

    def __init__(self, grid: GridWorld, raise_times: int) -> None:
        super().__init__(grid)
        self._raise_times = raise_times

    def grasp(self, world: WorldState, object_id: str):
        if self._raise_times > 0:
            self._raise_times -= 1
            raise RuntimeError("模拟机械臂驱动异常")
        return super().grasp(world, object_id)


def _runtime(backend, **kw):
    return AgentRuntime(backend, default_skill_manager(), MockPlanner(), **kw)


def test_transient_exception_recovers_via_retry():
    # Arrange：grasp 首次抛异常，重试可恢复
    grid, world = build_pick_and_place_world()
    memory = Memory()
    runtime = _runtime(_RaisingGraspBackend(grid, raise_times=1), max_retries=2, memory=memory)

    # Act
    report = runtime.run(GOAL, world)

    # Assert：闭环成功；异常被转为失败并单独留痕
    assert report.succeeded
    assert report.world.get("red_cube").in_container == "box"
    assert any("执行异常" in r.message and r.skill == "grasp" for r in report.trace)
    assert any(e.kind == "exception" for e in memory.episode())


def test_persistent_exception_fails_gracefully_without_crash():
    # Arrange：grasp 持续抛异常，重试与重规划都无法恢复
    grid, world = build_pick_and_place_world()
    runtime = _runtime(
        _RaisingGraspBackend(grid, raise_times=999), max_retries=1, max_replans=1
    )

    # Act：不应抛出异常
    report = runtime.run(GOAL, world)

    # Assert：优雅判定失败
    assert not report.succeeded
    assert report.task.status is TaskStatus.FAILED
    assert report.task.error


def test_ros2_backend_unavailable_does_not_crash_runtime():
    # Arrange：未接入真实 ROS2 时后端每个动作都抛 BackendNotAvailableError
    _, world = build_pick_and_place_world()
    runtime = _runtime(ROS2Backend(), max_retries=0, max_replans=0)

    # Act
    report = runtime.run(GOAL, world)

    # Assert：首个动作即异常，任务失败但运行时未崩溃
    assert not report.succeeded
    assert report.task.status is TaskStatus.FAILED
    assert any("执行异常" in r.message for r in report.trace)


def test_postcondition_exception_is_caught():
    # Arrange：技能返回成功，但后置条件校验抛异常也应被兜底为失败
    grid, world = build_pick_and_place_world()

    class _BadPostconditionBackend(SimBackend):
        pass

    manager = default_skill_manager()

    class _BoomSkill:
        name = "navigate"
        required_params = ()

        def preconditions(self, world, params):
            return True

        def execute(self, backend, world, params):
            return SkillResult.success("ok"), world

        def postconditions(self, world, params):
            raise RuntimeError("后置条件校验异常")

    # 用会在后置条件抛异常的技能替换 navigate
    manager._skills["navigate"] = _BoomSkill()  # type: ignore[assignment]
    runtime = AgentRuntime(
        _BadPostconditionBackend(grid), manager, MockPlanner(), max_retries=0, max_replans=0
    )

    # Act：不应崩溃
    report = runtime.run(GOAL, world)

    # Assert
    assert not report.succeeded
    assert report.task.status is TaskStatus.FAILED
