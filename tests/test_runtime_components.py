"""runtime 内部组件测试：hooks / planner pipeline / step executor。"""

from __future__ import annotations

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime import ExecutionContext
from robot_agent.runtime.agent_runtime import MemoryFailurePolicy
from robot_agent.skills import default_skill_manager
from robot_agent.tools import default_tool_registry
from robot_agent.world.grid_world import build_pick_and_place_world

GOAL = "把红色方块放到箱子里"


class _BrokenMemory:
    def record(self, kind, **fields):
        raise OSError("memory unavailable")


class _Recorder:
    def __init__(self) -> None:
        self.events = []

    def on_event(self, event) -> None:
        self.events.append(event)


def test_runtime_hooks_collects_diagnostic_in_best_effort_mode():
    from robot_agent.runtime.hooks import RuntimeHooks

    hooks = RuntimeHooks(
        memory=_BrokenMemory(),
        memory_failure_policy=MemoryFailurePolicy.BEST_EFFORT,
    )

    hooks.remember("task_started", goal=GOAL)

    diagnostics = hooks.diagnostics
    assert len(diagnostics) == 1
    assert diagnostics[0].component == "memory"
    assert diagnostics[0].stage == "task_started"
    assert diagnostics[0].error_type == "OSError"


def test_runtime_planner_prepares_goal_spec_and_scheduled_steps():
    from robot_agent.runtime.planner_pipeline import RuntimePlanner

    grid, world = build_pick_and_place_world()
    planner = RuntimePlanner(
        planner=MockPlanner(),
        skills=default_skill_manager(),
        tools=default_tool_registry(),
    )

    prepared = planner.prepare(GOAL, world)

    assert prepared.goal_spec.text == GOAL
    assert [step.step_id for step in prepared.steps] == [
        "navigate_object",
        "detect_object",
        "grasp_object",
        "navigate_container",
        "place_object",
    ]


def test_step_executor_retries_and_records_trace():
    from robot_agent.runtime.hooks import RuntimeHooks
    from robot_agent.runtime.step_executor import StepExecutor

    grid, world = build_pick_and_place_world(fail_actions={"grasp": 1})
    backend = SimBackend(grid)
    hooks = RuntimeHooks(observers=[_Recorder()])
    executor = StepExecutor(
        backend=backend,
        skills=default_skill_manager(),
        hooks=hooks,
        max_retries=2,
        tools=default_tool_registry(),
    )
    context = ExecutionContext()
    context.record("detect_object", {"object_ids": ["red_cube"]})
    plan = MockPlanner().plan(GOAL, world)
    grasp_step = next(
        step for step in plan.steps if getattr(step, "skill", "") == "grasp"
    )
    trace = []

    new_world, ok = executor.run_with_retry(
        grasp_step,
        world.with_robot_pose(world.get("red_cube").pose),
        trace,
        GOAL,
        context,
    )

    assert ok is True
    assert len(trace) == 2
    assert [record.status for record in trace] == ["failed", "ok"]
    assert new_world.holding == "red_cube"
    assert context.resolve_params({"object_id": grasp_step.params["object_id"]}) == {
        "object_id": "red_cube"
    }


class _BoomObserver:
    def on_event(self, event) -> None:
        raise RuntimeError("observer exploded")


def test_runtime_hooks_collects_observer_diagnostic_without_stopping_other_observers():
    from robot_agent.runtime.events import RuntimeEvent
    from robot_agent.runtime.hooks import RuntimeHooks

    _, world = build_pick_and_place_world()
    recorder = _Recorder()
    hooks = RuntimeHooks(observers=[_BoomObserver(), recorder])

    hooks.emit(RuntimeEvent("task_started", world=world, goal=GOAL))

    assert [event.kind for event in recorder.events] == ["task_started"]
    diagnostics = hooks.diagnostics
    assert len(diagnostics) == 1
    assert diagnostics[0].component == "observer"
    assert diagnostics[0].stage == "emit"
    assert diagnostics[0].error_type == "RuntimeError"
