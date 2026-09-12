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

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from robot_agent.backends.base import RobotBackend
from robot_agent.core.task import Task, TaskStatus
from robot_agent.core.types import SkillResult
from robot_agent.planning.base import Planner, SkillCall
from robot_agent.planning.goal import parse_goal
from robot_agent.runtime.events import RuntimeEvent, RuntimeObserver, StepRecord
from robot_agent.runtime.monitor import ExecutionMonitor
from robot_agent.runtime.task_manager import TaskManager
from robot_agent.skills.manager import SkillManager
from robot_agent.world.state import WorldState


class MemorySink(Protocol):
    """记忆写入接口（可选依赖，避免运行时与具体 Memory 实现耦合）。"""

    def record(self, kind: str, **fields: object) -> None: ...


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
        observers: Sequence[RuntimeObserver] | None = None,
        max_retries: int = 2,
        max_replans: int = 2,
    ) -> None:
        self._backend = backend
        self._skills = skill_manager
        self._planner = planner
        self._task_manager = task_manager or TaskManager()
        self._monitor = monitor or ExecutionMonitor()
        self._memory = memory
        self._observers = tuple(observers or ())
        self._max_retries = max_retries
        self._max_replans = max_replans

    def run(self, goal: str, world: WorldState) -> RunReport:
        """执行一个目标，返回运行报告。"""
        task = Task(goal).to(TaskStatus.RUNNING)
        self._remember("task_started", goal=goal)
        self._emit(RuntimeEvent("task_started", world=world, goal=goal, task=task))
        trace: list[StepRecord] = []
        replans = 0

        # 目标解析一次得到确定性判据；验证与规划从此解耦。
        try:
            goal_spec = parse_goal(goal, world)
        except Exception as exc:  # noqa: BLE001 - 运行时边界统一转换为失败报告
            return self._failure_report(
                task, world, trace, replans, goal, "目标解析失败", exc
            )

        try:
            plan = self._planner.plan(goal, world)
        except Exception as exc:  # noqa: BLE001 - 规划器属于可替换的外部边界
            return self._failure_report(
                task, world, trace, replans, goal, "规划失败", exc
            )

        while True:
            try:
                steps = self._task_manager.schedule(plan)
            except Exception as exc:  # noqa: BLE001 - 调度失败必须形成任务终态
                return self._failure_report(
                    task, world, trace, replans, goal, "调度失败", exc
                )
            world, failed = self._execute(steps, world, trace, goal)
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
            self._emit(
                RuntimeEvent(
                    "replan",
                    world=world,
                    goal=goal,
                    task=task,
                    replans=replans,
                    message=f"在 {failed.skill} 后重规划",
                )
            )
            try:
                plan = self._planner.plan(goal, world)
            except Exception as exc:  # noqa: BLE001 - 重规划失败必须形成任务终态
                return self._failure_report(
                    task, world, trace, replans, goal, "重规划失败", exc
                )
            task = task.to(TaskStatus.RUNNING)
            if plan.is_empty:
                break  # 重规划发现目标已达成

        if not task.is_terminal:
            try:
                goal_satisfied = self._monitor.verify_goal(goal_spec, world)
            except Exception as exc:  # noqa: BLE001 - 验证器属于可替换的运行时边界
                return self._failure_report(
                    task, world, trace, replans, goal, "目标验证失败", exc
                )
            if goal_satisfied:
                task = task.to(TaskStatus.SUCCEEDED)
                self._remember("task_succeeded", goal=goal)
            else:
                task = task.to(TaskStatus.FAILED, error="目标未达成")
                self._remember("task_failed", reason=task.error)

        self._emit(
            RuntimeEvent(
                "task_finished", world=world, goal=goal, task=task, replans=replans
            )
        )
        return RunReport(
            task=task, world=world, trace=tuple(trace), replans=replans
        )

    def _failure_report(
        self,
        task: Task,
        world: WorldState,
        trace: list[StepRecord],
        replans: int,
        goal: str,
        stage: str,
        exc: Exception,
    ) -> RunReport:
        """把阶段异常收敛为可观测的失败终态。"""
        error = f"{stage}（{type(exc).__name__}）：{exc}"
        failed_task = task.to(TaskStatus.FAILED, error=error)
        self._remember("task_failed", reason=error, stage=stage)
        self._emit(
            RuntimeEvent(
                "task_finished",
                world=world,
                goal=goal,
                task=failed_task,
                replans=replans,
                message=error,
            )
        )
        return RunReport(
            task=failed_task,
            world=world,
            trace=tuple(trace),
            replans=replans,
        )

    # --- 内部执行 ---

    def _execute(
        self,
        steps: list[SkillCall],
        world: WorldState,
        trace: list[StepRecord],
        goal: str,
    ) -> tuple[WorldState, SkillCall | None]:
        """顺序执行步骤，返回 (最新世界, 失败步骤或 None)。"""
        for step in steps:
            world, ok = self._run_with_retry(step, world, trace, goal)
            if not ok:
                return world, step
        return world, None

    def _run_with_retry(
        self,
        step: SkillCall,
        world: WorldState,
        trace: list[StepRecord],
        goal: str,
    ) -> tuple[WorldState, bool]:
        """执行单步，失败则原地重试至上限。"""
        attempt = 0
        while True:
            result, new_world, passed = self._try_step(step, world)
            record = StepRecord(
                skill=step.skill,
                params=dict(step.params),
                status="ok" if passed else "failed",
                message=result.message,
                attempt=attempt,
            )
            trace.append(record)
            self._remember(
                "step",
                skill=step.skill,
                passed=passed,
                message=result.message,
                attempt=attempt,
            )
            # 异常单独留痕，便于问题定位
            if "exception" in result.data:
                self._remember(
                    "exception", skill=step.skill, error=result.message, attempt=attempt
                )
            # 实时发出步骤事件，携带结果后的世界供上位机渲染
            self._emit(
                RuntimeEvent(
                    "step_result",
                    world=new_world if passed else world,
                    goal=goal,
                    step=record,
                )
            )
            if passed:
                return new_world, True
            attempt += 1
            if attempt > self._max_retries:
                return world, False  # 保持失败前的世界，交由重规划处理

    def _try_step(
        self, step: SkillCall, world: WorldState
    ) -> tuple[SkillResult, WorldState, bool]:
        """执行并判定单步；捕获一切异常转为失败，绝不向上抛。

        Returns:
            (结果, 新世界, 是否达标)。异常时世界保持不变、达标为 False。
        """
        try:
            result, new_world = self._skills.invoke(
                step.skill, self._backend, world, step.params
            )
            skill = self._skills.get(step.skill)
            passed = self._monitor.check(result, skill, world, new_world, step.params)
            return result, new_world, passed
        except Exception as exc:  # noqa: BLE001 - 刻意兜底，保证运行时不被异常终止
            failure = SkillResult.failure(
                f"执行异常（{type(exc).__name__}）：{exc}",
                exception=type(exc).__name__,
            )
            return failure, world, False

    def _remember(self, kind: str, **fields: object) -> None:
        if self._memory is not None:
            self._memory.record(kind, **fields)

    def _emit(self, event: RuntimeEvent) -> None:
        """向所有观察者广播事件；单个观察者异常不影响运行时与其它观察者。"""
        for observer in self._observers:
            try:
                observer.on_event(event)
            except Exception:  # noqa: BLE001 - 显示端故障不得拖垮机器人运行
                pass
