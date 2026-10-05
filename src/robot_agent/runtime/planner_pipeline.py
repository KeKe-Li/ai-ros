"""运行时规划准备流水线：目标解析、规划、验证与调度。"""

from __future__ import annotations

from dataclasses import dataclass

from robot_agent.core.errors import PlanningStageFailure
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
        try:
            resolved_goal = goal_spec or parse_goal(goal, world)
        except Exception as exc:  # noqa: BLE001 - 统一包装为带阶段语义的异常
            raise PlanningStageFailure("目标解析失败", exc) from exc

        try:
            plan = self._planner.plan(goal, world)
        except Exception as exc:  # noqa: BLE001 - 规划器属于可替换外部边界
            raise PlanningStageFailure("规划失败", exc) from exc

        try:
            self._plan_validator.validate(plan, resolved_goal, world)
        except Exception as exc:  # noqa: BLE001 - 无效计划不得进入调度阶段
            raise PlanningStageFailure("计划验证失败", exc) from exc

        try:
            steps = self._task_manager.schedule(plan)
        except Exception as exc:  # noqa: BLE001 - 调度失败必须有明确阶段归因
            raise PlanningStageFailure("调度失败", exc) from exc

        return PreparedPlan(goal_spec=resolved_goal, steps=steps)
