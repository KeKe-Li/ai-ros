"""Agent 主循环（AgentRuntime）。

编排完整闭环：理解 → 分解 → 调度 → 执行 → 监控 → 异常恢复 → 目标验证。

恢复策略：
    1) 单步失败先原地重试（最多 max_retries 次），应对瞬时故障；
    2) 重试仍失败则触发重规划——基于当前世界重新分解剩余目标（最多 max_replans 次）；
    3) 超出上限则任务判定为 FAILED。

健壮性：目标解析、规划、调度、技能/后端执行、后置条件和目标验证异常都会被
收敛为失败报告。单步异常走恢复流程，阶段异常直接形成可观测终态；这对接入
真实后端（如 ROS2，存在通信/超时/资源冲突）尤为关键。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from robot_agent.backends.base import RobotBackend
from robot_agent.core.errors import PlanningStageFailure
from robot_agent.core.task import Task, TaskStatus
from robot_agent.planning.base import Planner, PlanStep
from robot_agent.planning.validator import PlanValidator
from robot_agent.runtime.context import ExecutionContext
from robot_agent.runtime.events import (
    RuntimeDiagnostic,
    RuntimeEvent,
    RuntimeObserver,
    StepRecord,
)
from robot_agent.runtime.hooks import RuntimeHooks
from robot_agent.runtime.monitor import ExecutionMonitor
from robot_agent.runtime.planner_pipeline import PreparedPlan, RuntimePlanner
from robot_agent.runtime.step_executor import StepExecutor, step_name_for
from robot_agent.runtime.task_manager import TaskManager
from robot_agent.skills.manager import SkillManager
from robot_agent.tools.registry import ToolRegistry
from robot_agent.world.state import WorldState


class MemorySink(Protocol):
    """记忆写入接口（可选依赖，避免运行时与具体 Memory 实现耦合）。"""

    def record(self, kind: str, **fields: object) -> None: ...


class MemoryFailurePolicy(StrEnum):
    """可选 MemorySink 失败时的运行策略。"""

    BEST_EFFORT = "best_effort"
    RAISE = "raise"


@dataclass(frozen=True)
class RunReport:
    """一次运行的结果报告。"""

    task: Task
    world: WorldState
    initial_world: WorldState
    trace: tuple[StepRecord, ...] = field(default_factory=tuple)
    replans: int = 0
    diagnostics: tuple[RuntimeDiagnostic, ...] = field(default_factory=tuple)
    plan_history: tuple[tuple[PlanStep, ...], ...] = field(default_factory=tuple)

    @property
    def succeeded(self) -> bool:
        return self.task.status is TaskStatus.SUCCEEDED

    @property
    def goal(self) -> str:
        return self.task.goal


@dataclass(frozen=True)
class _ExecutionLoopFailure(Exception):
    stage: str
    cause: Exception
    task: Task
    world: WorldState
    replans: int


@dataclass(frozen=True)
class _RunState:
    """一次 run() 的运行不变量与累积缓冲。

    frozen 仅冻结属性引用；trace / plan_history 仍是执行过程中持续 append 的
    缓冲列表，沿用既有写法。集中这批不变量可避免在多层私有方法间反复透传。
    """

    goal: str
    initial_world: WorldState
    trace: list[StepRecord]
    plan_history: list[tuple[PlanStep, ...]]


class AgentRuntime:
    """机器人上层智能主循环。"""

    def __init__(
        self,
        backend: RobotBackend,
        skill_manager: SkillManager,
        planner: Planner,
        *,
        task_manager: TaskManager | None = None,
        monitor: ExecutionMonitor | None = None,
        tools: ToolRegistry | None = None,
        plan_validator: PlanValidator | None = None,
        memory: MemorySink | None = None,
        memory_failure_policy: MemoryFailurePolicy = MemoryFailurePolicy.BEST_EFFORT,
        observers: Sequence[RuntimeObserver] | None = None,
        max_retries: int = 2,
        max_replans: int = 2,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries 不能小于 0")
        if max_replans < 0:
            raise ValueError("max_replans 不能小于 0")
        self._monitor = monitor or ExecutionMonitor()
        self._hooks = RuntimeHooks(
            memory=memory,
            memory_failure_policy=memory_failure_policy,
            observers=observers,
        )
        self._runtime_planner = RuntimePlanner(
            planner=planner,
            skills=skill_manager,
            tools=tools,
            task_manager=task_manager,
            plan_validator=plan_validator,
        )
        self._step_executor = StepExecutor(
            backend=backend,
            skills=skill_manager,
            hooks=self._hooks,
            monitor=self._monitor,
            tools=tools,
            max_retries=max_retries,
        )
        self._max_replans = max_replans

    def run(self, goal: str, world: WorldState) -> RunReport:
        """执行一个目标，返回运行报告。"""
        self._hooks.reset()
        state = _RunState(
            goal=goal,
            initial_world=world,
            trace=[],
            plan_history=[],
        )
        task = Task(goal).to(TaskStatus.RUNNING)
        self._start_task(goal, world, task)

        try:
            prepared = self._prepare_plan(goal, world)
            self._remember_plan(state, prepared)
        except PlanningStageFailure as exc:
            return self._failure_report(state, task, world, 0, exc.stage, exc.cause)
        except Exception as exc:  # noqa: BLE001 - 兜底保留运行时边界
            return self._failure_report(state, task, world, 0, "规划失败", exc)

        goal_spec = prepared.goal_spec
        try:
            task, world, replans = self._execute_plan_loop(
                state, world, task, goal_spec, prepared.steps
            )
        except _ExecutionLoopFailure as exc:
            return self._failure_report(
                state, exc.task, exc.world, exc.replans, exc.stage, exc.cause
            )

        if not task.is_terminal:
            try:
                task = self._finalize_task(goal, task, world, goal_spec)
            except Exception as exc:  # noqa: BLE001 - 验证器属于可替换的运行时边界
                return self._failure_report(
                    state, task, world, replans, "目标验证失败", exc
                )

        self._hooks.emit(
            RuntimeEvent(
                "task_finished", world=world, goal=goal, task=task, replans=replans
            )
        )
        return self._build_report(state, task, world, replans)

    def _start_task(self, goal: str, world: WorldState, task: Task) -> None:
        self._hooks.remember("task_started", goal=goal)
        self._hooks.emit(
            RuntimeEvent("task_started", world=world, goal=goal, task=task)
        )

    def _prepare_plan(self, goal: str, world: WorldState):
        return self._runtime_planner.prepare(goal, world)

    @staticmethod
    def _remember_plan(state: _RunState, prepared: PreparedPlan) -> None:
        state.plan_history.append(tuple(prepared.steps))

    def _execute_plan_loop(
        self,
        state: _RunState,
        world: WorldState,
        task: Task,
        goal_spec: object,
        steps: list[object],
    ) -> tuple[Task, WorldState, int]:
        goal = state.goal
        replans = 0
        while True:
            context = ExecutionContext()
            world, failed = self._step_executor.execute(
                steps, world, state.trace, goal, context
            )
            if failed is None:
                return task, world, replans
            if replans >= self._max_replans:
                failed_name = step_name_for(failed)
                task = task.to(
                    TaskStatus.FAILED,
                    error=f"步骤失败且超出重规划上限：{failed_name}",
                )
                self._hooks.remember("task_failed", reason=task.error)
                return task, world, replans
            replans += 1
            task = self._announce_replan(goal, world, task, replans, failed)
            try:
                prepared = self._runtime_planner.prepare(
                    goal, world, goal_spec=goal_spec
                )
                self._remember_plan(state, prepared)
            except PlanningStageFailure as exc:
                raise _ExecutionLoopFailure(
                    stage="重规划失败",
                    cause=exc.cause,
                    task=task,
                    world=world,
                    replans=replans,
                ) from exc
            except Exception as exc:  # noqa: BLE001 - 重规划失败必须形成任务终态
                raise _ExecutionLoopFailure(
                    stage="重规划失败",
                    cause=exc,
                    task=task,
                    world=world,
                    replans=replans,
                ) from exc
            task = task.to(TaskStatus.RUNNING)
            steps = prepared.steps
            if not steps:
                return task, world, replans

    def _announce_replan(
        self,
        goal: str,
        world: WorldState,
        task: Task,
        replans: int,
        failed_step,
    ) -> Task:
        recovering_task = task.to(TaskStatus.RECOVERING)
        failed_name = step_name_for(failed_step)
        self._hooks.remember("replan", attempt=replans, after_skill=failed_name)
        self._hooks.emit(
            RuntimeEvent(
                "replan",
                world=world,
                goal=goal,
                task=recovering_task,
                replans=replans,
                message=f"在 {failed_name} 后重规划",
            )
        )
        return recovering_task

    def _finalize_task(
        self,
        goal: str,
        task: Task,
        world: WorldState,
        goal_spec,
    ) -> Task:
        goal_satisfied = self._monitor.verify_goal(goal_spec, world)
        if goal_satisfied:
            succeeded_task = task.to(TaskStatus.SUCCEEDED)
            self._hooks.remember("task_succeeded", goal=goal)
            return succeeded_task
        failed_task = task.to(TaskStatus.FAILED, error="目标未达成")
        self._hooks.remember("task_failed", reason=failed_task.error)
        return failed_task

    def _build_report(
        self,
        state: _RunState,
        task: Task,
        world: WorldState,
        replans: int,
    ) -> RunReport:
        return RunReport(
            task=task,
            world=world,
            initial_world=state.initial_world,
            trace=tuple(state.trace),
            replans=replans,
            diagnostics=self._hooks.diagnostics,
            plan_history=tuple(state.plan_history),
        )

    def _failure_report(
        self,
        state: _RunState,
        task: Task,
        world: WorldState,
        replans: int,
        stage: str,
        exc: Exception,
    ) -> RunReport:
        """把阶段异常收敛为可观测的失败终态。"""
        error = f"{stage}（{type(exc).__name__}）：{exc}"
        failed_task = task.to(TaskStatus.FAILED, error=error)
        self._hooks.remember("task_failed", reason=error, stage=stage)
        self._hooks.emit(
            RuntimeEvent(
                "task_finished",
                world=world,
                goal=state.goal,
                task=failed_task,
                replans=replans,
                message=error,
            )
        )
        return self._build_report(state, failed_task, world, replans)
