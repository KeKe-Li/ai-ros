"""运行时规划准备流水线：目标解析、规划、验证与调度。"""

from __future__ import annotations

from dataclasses import dataclass

from robot_agent.planning.base import Planner, PlanStep
from robot_agent.planning.goal import GoalSpec, parse_goal
from robot_agent.planning.validator import PlanValidator
from robot_agent.runtime.task_manager import TaskManager
from robot_agent.skills.manager import SkillManager
from robot_agent.tools.registry import ToolRegistry
from robot_agent.world.state import WorldState


@dataclass(frozen=True)
class PreparedPlan:
    """已通过校验且排好执行顺序的计划。"""

    goal_spec: GoalSpec
    steps: list[PlanStep]


class RuntimePlanner:
    """把 goal + world 转成可直接执行的有序步骤列表。"""

    def __init__(
        self,
        *,
        planner: Planner,
        skills: SkillManager,
        tools: ToolRegistry | None = None,
        task_manager: TaskManager | None = None,
        plan_validator: PlanValidator | None = None,
    ) -> None:
        self._planner = planner
        self._task_manager = task_manager or TaskManager()
        self._plan_validator = plan_validator or PlanValidator(skills, tools)

    def prepare(
        self, goal: str, world: WorldState, goal_spec: GoalSpec | None = None
    ) -> PreparedPlan:
        resolved_goal = goal_spec or parse_goal(goal, world)
        plan = self._planner.plan(goal, world)
        self._plan_validator.validate(plan, resolved_goal, world)
        steps = self._task_manager.schedule(plan)
        return PreparedPlan(goal_spec=resolved_goal, steps=steps)
