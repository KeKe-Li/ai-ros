"""runtime 内部组件测试：hooks / planner pipeline / step executor。"""

from __future__ import annotations

from robot_agent.backends.sim_backend import SimBackend
from robot_agent.core.task import Task, TaskStatus
from robot_agent.core.types import SkillResult
from robot_agent.planning.base import OutputRef, SkillCall, ToolCall
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.runtime import ExecutionContext
from robot_agent.runtime.agent_runtime import MemoryFailurePolicy
from robot_agent.runtime.events import RuntimeDiagnostic
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


def test_step_executor_classifies_output_resolution_failure():
    from robot_agent.runtime.hooks import RuntimeHooks
    from robot_agent.runtime.step_executor import StepExecutor

    grid, world = build_pick_and_place_world()
    executor = StepExecutor(
        backend=SimBackend(grid),
        skills=default_skill_manager(),
        hooks=RuntimeHooks(),
        max_retries=0,
        tools=default_tool_registry(),
    )
    trace = []

    _, ok = executor.run_with_retry(
        SkillCall(
            "grasp",
            {"object_id": OutputRef("missing", path=("object_ids", 0))},
            step_id="grasp_object",
        ),
        world,
        trace,
        GOAL,
        ExecutionContext(),
    )

    assert ok is False
    assert trace[0].failure_kind == "resolve_params_failed"
    assert trace[0].error_type == "OutputResolutionError"


def test_step_executor_classifies_tool_invocation_failure():
    from robot_agent.runtime.hooks import RuntimeHooks
    from robot_agent.runtime.step_executor import StepExecutor

    grid, world = build_pick_and_place_world()
    tools = default_tool_registry()
    tools.register(
        "explode",
        "模拟失败工具",
        lambda world: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    executor = StepExecutor(
        backend=SimBackend(grid),
        skills=default_skill_manager(),
        hooks=RuntimeHooks(),
        max_retries=0,
        tools=tools,
    )
    trace = []

    _, ok = executor.run_with_retry(
        ToolCall("explode", step_id="explode_tool"),
        world,
        trace,
        GOAL,
        ExecutionContext(),
    )

    assert ok is False
    assert trace[0].failure_kind == "tool_invoke_failed"
    assert trace[0].error_type == "RuntimeError"


def test_step_executor_classifies_postcondition_failure_without_exception():
    from robot_agent.runtime.hooks import RuntimeHooks
    from robot_agent.runtime.step_executor import StepExecutor

    class _FalsePostconditionSkill:
        name = "navigate"
        required_params = ()

        def capability_spec(self):
            return default_skill_manager().get("navigate").capability_spec()

        def preconditions(self, world, params):
            return True

        def execute(self, backend, world, params):
            from robot_agent.core.types import SkillResult

            target = world.get(params["target_object"]).pose
            result, new_world = backend.navigate_to(world, target)
            return SkillResult.success("已导航") if result.ok else result, new_world

        def postconditions(self, before, after, params, result):
            return False

    grid, world = build_pick_and_place_world()
    manager = default_skill_manager()
    manager._skills["navigate"] = _FalsePostconditionSkill()  # type: ignore[assignment]
    executor = StepExecutor(
        backend=SimBackend(grid),
        skills=manager,
        hooks=RuntimeHooks(),
        max_retries=0,
        tools=default_tool_registry(),
    )
    trace = []

    _, ok = executor.run_with_retry(
        SkillCall("navigate", {"target_object": "red_cube"}, step_id="navigate_object"),
        world,
        trace,
        GOAL,
        ExecutionContext(),
    )

    assert ok is False
    assert trace[0].failure_kind == "postcondition_failed"
    assert trace[0].error_type is None


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


def test_agent_runtime_build_report_preserves_trace_and_diagnostics():
    from robot_agent.runtime.agent_runtime import AgentRuntime
    from robot_agent.runtime.events import StepRecord
    from robot_agent.runtime.hooks import RuntimeHooks

    grid, world = build_pick_and_place_world()
    runtime = AgentRuntime(
        SimBackend(grid),
        default_skill_manager(),
        MockPlanner(),
    )
    runtime._hooks = RuntimeHooks()  # type: ignore[assignment]
    runtime._hooks._diagnostics.append(  # type: ignore[attr-defined]
        RuntimeDiagnostic(
            component="memory",
            stage="task_started",
            error_type="OSError",
            message="boom",
        )
    )
    trace = [StepRecord("navigate", {"target_object": "red_cube"}, "ok", "已导航", 0)]

    report = runtime._build_report(  # type: ignore[attr-defined]
        Task(GOAL).to(TaskStatus.RUNNING).to(TaskStatus.SUCCEEDED),
        world,
        trace,
        replans=1,
    )

    assert report.succeeded
    assert report.trace == tuple(trace)
    assert report.replans == 1
    assert report.diagnostics[0].error_type == "OSError"


def test_step_executor_builds_step_record_from_attempt_data():
    from robot_agent.runtime.hooks import RuntimeHooks
    from robot_agent.runtime.step_executor import StepAttempt, StepExecutor

    grid, world = build_pick_and_place_world()
    executor = StepExecutor(
        backend=SimBackend(grid),
        skills=default_skill_manager(),
        hooks=RuntimeHooks(),
        max_retries=0,
        tools=default_tool_registry(),
    )
    step = ToolCall("locate_object", {"object_id": "red_cube"}, step_id="locate")
    attempt = StepAttempt(
        result=SkillResult.success("工具调用成功：locate_object", value="red_cube"),
        world=world,
        passed=True,
        resolved_params={"object_id": "red_cube"},
    )

    record = executor._build_step_record(step, attempt, attempt_index=0)  # type: ignore[attr-defined]

    assert record.skill == "tool:locate_object"
    assert record.kind == "tool"
    assert record.step_id == "locate"
    assert record.output == {"value": "red_cube"}
