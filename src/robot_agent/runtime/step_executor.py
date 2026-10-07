"""单步执行与重试逻辑。"""

from __future__ import annotations

from dataclasses import dataclass

from robot_agent.backends.base import RobotBackend
from robot_agent.core.errors import OutputResolutionError
from robot_agent.core.types import SkillResult
from robot_agent.planning.base import PlanStep, SkillCall, ToolCall
from robot_agent.runtime.context import ExecutionContext
from robot_agent.runtime.events import RuntimeEvent, StepRecord
from robot_agent.runtime.hooks import RuntimeHooks
from robot_agent.runtime.monitor import ExecutionMonitor
from robot_agent.skills.manager import SkillManager
from robot_agent.tools.registry import ToolRegistry
from robot_agent.world.state import WorldState


@dataclass(frozen=True)
class StepAttempt:
    """一次步骤尝试的统一结果。"""

    result: SkillResult
    world: WorldState
    passed: bool
    resolved_params: dict[str, object]
    error_type: str | None = None
    failure_kind: str | None = None


class StepExecutor:
    """执行计划步骤，负责异常收敛、留痕和重试。"""

    def __init__(
        self,
        *,
        backend: RobotBackend,
        skills: SkillManager,
        hooks: RuntimeHooks,
        monitor: ExecutionMonitor | None = None,
        tools: ToolRegistry | None = None,
        max_retries: int = 2,
    ) -> None:
        self._backend = backend
        self._skills = skills
        self._hooks = hooks
        self._monitor = monitor or ExecutionMonitor()
        self._tools = tools
        self._max_retries = max_retries

    def execute(
        self,
        steps: list[PlanStep],
        world: WorldState,
        trace: list[StepRecord],
        goal: str,
        context: ExecutionContext,
    ) -> tuple[WorldState, PlanStep | None]:
        for step in steps:
            world, ok = self.run_with_retry(step, world, trace, goal, context)
            if not ok:
                return world, step
        return world, None

    def run_with_retry(
        self,
        step: PlanStep,
        world: WorldState,
        trace: list[StepRecord],
        goal: str,
        context: ExecutionContext,
    ) -> tuple[WorldState, bool]:
        attempt = 0
        while True:
            outcome = self._try_step(step, world, context)
            record = self._build_step_record(step, outcome, attempt_index=attempt)
            trace.append(record)
            self._remember_attempt(record, outcome)
            self._emit_step_result(goal, world, record, outcome)
            if outcome.passed:
                context.record(step.step_id, outcome.result.data)
                return outcome.world, True
            attempt += 1
            if attempt > self._max_retries:
                return world, False

    def _build_step_record(
        self,
        step: PlanStep,
        outcome: StepAttempt,
        *,
        attempt_index: int,
    ) -> StepRecord:
        return StepRecord(
            skill=step_name_for(step),
            params=outcome.resolved_params,
            status="ok" if outcome.passed else "failed",
            message=outcome.result.message,
            attempt=attempt_index,
            step_id=step.step_id,
            kind="skill" if isinstance(step, SkillCall) else "tool",
            raw_params=step.params,
            output=outcome.result.data,
            error_type=outcome.error_type,
            failure_kind=outcome.failure_kind,
        )

    def _remember_attempt(self, record: StepRecord, outcome: StepAttempt) -> None:
        self._hooks.remember(
            "step",
            skill=record.skill,
            passed=outcome.passed,
            message=record.message,
            attempt=record.attempt,
            failure_kind=record.failure_kind,
        )
        if outcome.error_type is not None:
            self._hooks.remember(
                "exception",
                skill=record.skill,
                error=record.message,
                attempt=record.attempt,
                error_type=outcome.error_type,
                failure_kind=record.failure_kind,
            )

    def _emit_step_result(
        self,
        goal: str,
        world: WorldState,
        record: StepRecord,
        outcome: StepAttempt,
    ) -> None:
        self._hooks.emit(
            RuntimeEvent(
                "step_result",
                world=outcome.world if outcome.passed else world,
                goal=goal,
                step=record,
            )
        )

    def _try_step(
        self, step: PlanStep, world: WorldState, context: ExecutionContext
    ) -> StepAttempt:
        resolved_params: dict[str, object] = {}
        try:
            resolved_params = context.resolve_params(step.params)
        except OutputResolutionError as exc:
            return self._failed_attempt(
                world,
                resolved_params,
                failure_kind="resolve_params_failed",
                stage="执行异常",
                exc=exc,
            )

        if isinstance(step, SkillCall):
            return self._run_skill(step, world, resolved_params)
        if isinstance(step, ToolCall):
            return self._run_tool(step, world, resolved_params)
        return self._failed_attempt(
            world,
            resolved_params,
            failure_kind="unsupported_step_type",
            stage="步骤类型异常",
            exc=TypeError(f"不支持的步骤类型：{type(step).__name__}"),
        )

    def _run_skill(
        self,
        step: SkillCall,
        world: WorldState,
        resolved_params: dict[str, object],
    ) -> StepAttempt:
        try:
            result, new_world = self._skills.invoke(
                step.skill, self._backend, world, resolved_params
            )
        except Exception as exc:  # noqa: BLE001 - 技能属于可替换运行边界
            return self._failed_attempt(
                world,
                resolved_params,
                failure_kind="skill_invoke_failed",
                stage="执行异常",
                exc=exc,
            )

        try:
            skill = self._skills.get(step.skill)
            passed = self._monitor.check(
                result, skill, world, new_world, resolved_params
            )
        except Exception as exc:  # noqa: BLE001 - 后置条件/监控异常必须被收敛
            return self._failed_attempt(
                world,
                resolved_params,
                failure_kind="postcondition_failed",
                stage="执行异常",
                exc=exc,
            )

        failure_kind = None
        if not passed:
            failure_kind = (
                "postcondition_failed" if result.ok else "skill_execution_failed"
            )
        return StepAttempt(
            result=result,
            world=new_world,
            passed=passed,
            resolved_params=resolved_params,
            failure_kind=failure_kind,
        )

    def _run_tool(
        self,
        step: ToolCall,
        world: WorldState,
        resolved_params: dict[str, object],
    ) -> StepAttempt:
        if self._tools is None:
            return self._failed_attempt(
                world,
                resolved_params,
                failure_kind="tool_invoke_failed",
                stage="执行异常",
                exc=RuntimeError("运行时未配置工具注册表"),
            )
        try:
            value = self._tools.call(step.tool, world, **resolved_params)
        except Exception as exc:  # noqa: BLE001 - 工具调用异常收敛为失败轨迹
            return self._failed_attempt(
                world,
                resolved_params,
                failure_kind="tool_invoke_failed",
                stage="执行异常",
                exc=exc,
            )
        result = SkillResult.success(f"工具调用成功：{step.tool}", value=value)
        return StepAttempt(
            result=result,
            world=world,
            passed=True,
            resolved_params=resolved_params,
        )

    @staticmethod
    def _failed_attempt(
        world: WorldState,
        resolved_params: dict[str, object],
        *,
        failure_kind: str,
        stage: str,
        exc: Exception,
    ) -> StepAttempt:
        result = SkillResult.failure(
            f"{stage}（{type(exc).__name__}）：{exc}",
            exception=type(exc).__name__,
            failure_kind=failure_kind,
        )
        return StepAttempt(
            result=result,
            world=world,
            passed=False,
            resolved_params=resolved_params,
            error_type=type(exc).__name__,
            failure_kind=failure_kind,
        )


def step_name_for(step: PlanStep) -> str:
    """返回适合轨迹与诊断展示的步骤名称。"""
    if isinstance(step, SkillCall):
        return step.skill
    return f"tool:{step.tool}"
