"""单步执行与重试逻辑。"""

from __future__ import annotations

from robot_agent.backends.base import RobotBackend
from robot_agent.core.types import SkillResult
from robot_agent.planning.base import PlanStep, SkillCall, ToolCall
from robot_agent.runtime.context import ExecutionContext
from robot_agent.runtime.events import RuntimeEvent, StepRecord
from robot_agent.runtime.hooks import RuntimeHooks
from robot_agent.runtime.monitor import ExecutionMonitor
from robot_agent.skills.manager import SkillManager
from robot_agent.tools.registry import ToolRegistry
from robot_agent.world.state import WorldState


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
            result, new_world, passed, resolved_params = self._try_step(
                step, world, context
            )
            step_name = step_name_for(step)
            record = StepRecord(
                skill=step_name,
                params=resolved_params,
                status="ok" if passed else "failed",
                message=result.message,
                attempt=attempt,
                step_id=step.step_id,
                kind="skill" if isinstance(step, SkillCall) else "tool",
                raw_params=step.params,
                output=result.data,
                error_type=(
                    str(result.data["exception"])
                    if "exception" in result.data
                    else None
                ),
            )
            trace.append(record)
            self._hooks.remember(
                "step",
                skill=step_name,
                passed=passed,
                message=result.message,
                attempt=attempt,
            )
            if "exception" in result.data:
                self._hooks.remember(
                    "exception", skill=step_name, error=result.message, attempt=attempt
                )
            self._hooks.emit(
                RuntimeEvent(
                    "step_result",
                    world=new_world if passed else world,
                    goal=goal,
                    step=record,
                )
            )
            if passed:
                context.record(step.step_id, result.data)
                return new_world, True
            attempt += 1
            if attempt > self._max_retries:
                return world, False

    def _try_step(
        self, step: PlanStep, world: WorldState, context: ExecutionContext
    ) -> tuple[SkillResult, WorldState, bool, dict[str, object]]:
        resolved_params: dict[str, object] = {}
        try:
            resolved_params = context.resolve_params(step.params)
            if isinstance(step, SkillCall):
                result, new_world = self._skills.invoke(
                    step.skill, self._backend, world, resolved_params
                )
                skill = self._skills.get(step.skill)
                passed = self._monitor.check(
                    result, skill, world, new_world, resolved_params
                )
            elif isinstance(step, ToolCall):
                if self._tools is None:
                    raise RuntimeError("运行时未配置工具注册表")
                value = self._tools.call(step.tool, world, **resolved_params)
                result = SkillResult.success(f"工具调用成功：{step.tool}", value=value)
                new_world = world
                passed = True
            else:
                raise TypeError(f"不支持的步骤类型：{type(step).__name__}")
            return result, new_world, passed, resolved_params
        except Exception as exc:  # noqa: BLE001 - 刻意兜底，保证运行时不被异常终止
            failure = SkillResult.failure(
                f"执行异常（{type(exc).__name__}）：{exc}",
                exception=type(exc).__name__,
            )
            return failure, world, False, resolved_params


def step_name_for(step: PlanStep) -> str:
    """返回适合轨迹与诊断展示的步骤名称。"""
    if isinstance(step, SkillCall):
        return step.skill
    return f"tool:{step.tool}"
