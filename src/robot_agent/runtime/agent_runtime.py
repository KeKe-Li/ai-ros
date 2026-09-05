"""Agent 主循环（AgentRuntime）。

编排完整闭环：理解 → 分解 → 调度 → 执行 → 监控 → 异常恢复 → 目标验证。

恢复策略：
    1) 单步失败先原地重试（最多 max_retries 次），应对瞬时故障；
    2) 重试仍失败则触发重规划——基于当前世界重新分解剩余目标（最多 max_replans 次）；
    3) 超出上限则任务判定为 FAILED。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from robot_agent.backends.base import RobotBackend
from robot_agent.core.task import Task, TaskStatus
from robot_agent.core.types import SkillResult
from robot_agent.planning.base import Planner, SkillCall
from robot_agent.runtime.monitor import ExecutionMonitor
from robot_agent.runtime.task_manager import TaskManager
from robot_agent.skills.manager import SkillManager
from robot_agent.world.state import WorldState


class MemorySink(Protocol):
    """记忆写入接口（可选依赖，避免运行时与具体 Memory 实现耦合）。"""

    def record(self, kind: str, **fields: object) -> None: ...


@dataclass(frozen=True)
class StepRecord:
    """单步执行留痕，用于追溯与展示闭环过程。"""

    skill: str
    params: dict[str, object]
    status: str
    message: str
    attempt: int


@dataclass(frozen=True)
class RunReport:
    """一次运行的结果报告。"""

    task: Task
    world: WorldState
    trace: tuple[StepRecord, ...] = field(default_factory=tuple)
    replans: int = 0

    @property
    def succeeded(self) -> bool:
        return self.task.status is TaskStatus.SUCCEEDED


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
        memory: MemorySink | None = None,
        max_retries: int = 2,
        max_replans: int = 2,
    ) -> None:
        self._backend = backend
        self._skills = skill_manager
        self._planner = planner
        self._task_manager = task_manager or TaskManager()
        self._monitor = monitor or ExecutionMonitor()
        self._memory = memory
        self._max_retries = max_retries
        self._max_replans = max_replans

    def run(self, goal: str, world: WorldState) -> RunReport:
        """执行一个目标，返回运行报告。"""
        task = Task(goal).to(TaskStatus.RUNNING)
        self._remember("task_started", goal=goal)
        trace: list[StepRecord] = []
        replans = 0

        plan = self._planner.plan(goal, world)
        while True:
            steps = self._task_manager.schedule(plan)
            world, failed = self._execute(steps, world, trace)
            if failed is None:
                break  # 所有步骤达标
            # 单步在重试后仍失败 → 尝试重规划
            if replans >= self._max_replans:
                task = task.to(TaskStatus.FAILED, error=f"步骤失败且超出重规划上限：{failed.skill}")
                self._remember("task_failed", reason=task.error)
                break
            replans += 1
            task = task.to(TaskStatus.RECOVERING)
            self._remember("replan", attempt=replans, after_skill=failed.skill)
            plan = self._planner.plan(goal, world)
            task = task.to(TaskStatus.RUNNING)
            if plan.is_empty:
                break  # 重规划发现目标已达成

        if not task.is_terminal:
            if self._monitor.verify_goal(self._planner, goal, world):
                task = task.to(TaskStatus.SUCCEEDED)
                self._remember("task_succeeded", goal=goal)
            else:
                task = task.to(TaskStatus.FAILED, error="目标未达成")
                self._remember("task_failed", reason=task.error)

        return RunReport(
            task=task, world=world, trace=tuple(trace), replans=replans
        )

    # --- 内部执行 ---

    def _execute(
        self, steps: list[SkillCall], world: WorldState, trace: list[StepRecord]
    ) -> tuple[WorldState, SkillCall | None]:
        """顺序执行步骤，返回 (最新世界, 失败步骤或 None)。"""
        for step in steps:
            world, ok = self._run_with_retry(step, world, trace)
            if not ok:
                return world, step
        return world, None

    def _run_with_retry(
        self, step: SkillCall, world: WorldState, trace: list[StepRecord]
    ) -> tuple[WorldState, bool]:
        """执行单步，失败则原地重试至上限。"""
        skill = self._skills.get(step.skill)
        attempt = 0
        while True:
            result, new_world = self._skills.invoke(
                step.skill, self._backend, world, step.params
            )
            passed = self._monitor.check(result, skill, new_world, step.params)
            trace.append(
                StepRecord(
                    skill=step.skill,
                    params=dict(step.params),
                    status="ok" if passed else "failed",
                    message=result.message,
                    attempt=attempt,
                )
            )
            self._remember(
                "step",
                skill=step.skill,
                passed=passed,
                message=result.message,
                attempt=attempt,
            )
            if passed:
                return new_world, True
            attempt += 1
            if attempt > self._max_retries:
                return world, False  # 保持失败前的世界，交由重规划处理

    def _remember(self, kind: str, **fields: object) -> None:
        if self._memory is not None:
            self._memory.record(kind, **fields)
