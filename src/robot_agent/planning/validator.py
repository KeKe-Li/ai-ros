"""计划执行前的结构、引用与目标一致性验证。"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from robot_agent.core.errors import PlanningError, UnknownSkillError
from robot_agent.planning.base import OutputRef, Plan, SkillCall, ToolCall
from robot_agent.planning.goal import GoalSpec, InContainerGoal
from robot_agent.skills.manager import SkillManager
from robot_agent.tools.registry import ToolRegistry
from robot_agent.world.state import WorldState


class PlanValidator:
    """在计划进入调度器前拒绝结构错误或偏离目标的步骤。"""

    def __init__(
        self,
        skills: SkillManager,
        tools: ToolRegistry | None = None,
        *,
        max_steps: int = 64,
    ) -> None:
        self._skills = skills
        self._tools = tools
        self._max_steps = max_steps

    def validate(self, plan: Plan, goal: GoalSpec, world: WorldState) -> None:
        """验证计划；发现错误时在执行任何步骤前抛出 `PlanningError`。"""
        if isinstance(goal, InContainerGoal) and plan.goal != goal.text:
            raise PlanningError("计划目标与当前任务目标不一致")
        if len(plan.steps) > self._max_steps:
            raise PlanningError(f"计划步骤过多：{len(plan.steps)} > {self._max_steps}")
        if not plan.steps:
            if not goal.is_satisfied(world):
                raise PlanningError("目标尚未满足，但规划器返回了空计划")
            return

        step_ids = [step.step_id for step in plan.steps]
        if any(not step_id.strip() for step_id in step_ids):
            raise PlanningError("所有计划步骤都必须具有非空 step_id")
        if len(set(step_ids)) != len(step_ids):
            raise PlanningError("计划中存在重复 step_id")

        id_to_index = {step_id: index for index, step_id in enumerate(step_ids)}
        self._validate_dependencies(plan)
        for index, step in enumerate(plan.steps):
            if not isinstance(step.params, Mapping):
                raise PlanningError(f"步骤 {step.step_id} 的 params 必须是映射")
            self._validate_refs(step, index, id_to_index)
            if isinstance(step, SkillCall):
                self._validate_skill(step, goal, world)
            elif isinstance(step, ToolCall):
                self._validate_tool(step)
            else:
                raise PlanningError(f"不支持的计划步骤类型：{type(step).__name__}")

    @staticmethod
    def _validate_dependencies(plan: Plan) -> None:
        size = len(plan.steps)
        indegree = [0] * size
        adjacency: list[list[int]] = [[] for _ in range(size)]
        for index, step in enumerate(plan.steps):
            for dependency in step.depends_on:
                if dependency < 0 or dependency >= size or dependency == index:
                    raise PlanningError(
                        f"步骤 {step.step_id} 存在非法依赖：{dependency}"
                    )
                adjacency[dependency].append(index)
                indegree[index] += 1

        ready = [index for index, degree in enumerate(indegree) if degree == 0]
        visited = 0
        while ready:
            current = ready.pop()
            visited += 1
            for following in adjacency[current]:
                indegree[following] -= 1
                if indegree[following] == 0:
                    ready.append(following)
        if visited != size:
            raise PlanningError("计划存在循环依赖")

    def _validate_refs(
        self, step: SkillCall | ToolCall, index: int, id_to_index: dict[str, int]
    ) -> None:
        for ref in _iter_refs(step.params):
            source_index = id_to_index.get(ref.step_id)
            if source_index is None:
                raise PlanningError(
                    f"步骤 {step.step_id} 引用了不存在的步骤：{ref.step_id}"
                )
            if source_index >= index:
                raise PlanningError(
                    f"步骤 {step.step_id} 只能引用更早步骤的输出：{ref.step_id}"
                )
            if source_index not in step.depends_on:
                raise PlanningError(
                    f"步骤 {step.step_id} 引用了 {ref.step_id}，但未声明直接依赖"
                )
            if not ref.path:
                raise PlanningError(f"步骤 {step.step_id} 的输出引用路径不能为空")

    def _validate_skill(
        self, step: SkillCall, goal: GoalSpec, world: WorldState
    ) -> None:
        try:
            skill = self._skills.get(step.skill)
        except UnknownSkillError as exc:
            raise PlanningError(str(exc)) from exc

        missing = [name for name in skill.required_params if name not in step.params]
        if missing:
            raise PlanningError(f"步骤 {step.step_id} 缺少必需参数：{missing}")

        if not isinstance(goal, InContainerGoal):
            return
        if step.skill == "navigate":
            self._validate_known_entity(step, "target_object", world)
            value = step.params.get("target_object")
            entity_id = value.expected if isinstance(value, OutputRef) else value
            if entity_id not in {goal.object_id, goal.container_id}:
                raise PlanningError(
                    f"步骤 {step.step_id} 的导航目标与任务无关：{entity_id!r}"
                )
        elif step.skill == "detect" and "object_id" in step.params:
            self._validate_goal_entity(step, "object_id", goal.object_id)
        elif step.skill == "grasp":
            value = step.params["object_id"]
            if not isinstance(value, OutputRef):
                raise PlanningError(
                    f"步骤 {step.step_id} 的抓取对象必须使用感知或工具输出引用"
                )
            self._validate_goal_entity(step, "object_id", goal.object_id)
        elif step.skill == "place":
            self._validate_goal_entity(step, "container_id", goal.container_id)

    def _validate_tool(self, step: ToolCall) -> None:
        if self._tools is None or step.tool not in self._tools.names():
            raise PlanningError(f"未注册的工具：{step.tool}")

    @staticmethod
    def _validate_known_entity(
        step: SkillCall, parameter: str, world: WorldState
    ) -> None:
        value = step.params.get(parameter)
        entity_id = value.expected if isinstance(value, OutputRef) else value
        if not isinstance(entity_id, str) or world.get(entity_id) is None:
            raise PlanningError(
                f"步骤 {step.step_id} 引用了不存在的实体：{entity_id!r}"
            )

    @staticmethod
    def _validate_goal_entity(
        step: SkillCall, parameter: str, expected: str
    ) -> None:
        value = step.params.get(parameter)
        entity_id = value.expected if isinstance(value, OutputRef) else value
        if entity_id != expected:
            raise PlanningError(
                f"步骤 {step.step_id} 的 {parameter} 不符合目标物体或容器："
                f"{entity_id!r} != {expected!r}"
            )


def _iter_refs(value: Any) -> Iterator[OutputRef]:
    if isinstance(value, OutputRef):
        yield value
    elif isinstance(value, Mapping):
        for item in value.values():
            yield from _iter_refs(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _iter_refs(item)
