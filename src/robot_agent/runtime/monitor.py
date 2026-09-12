"""执行监控与异常恢复策略（ExecutionMonitor）。

职责聚焦于"判断"与"策略"，不负责编排：
    - check：单步执行后是否达标（结果成功且执行前后状态满足后置条件）。
    - verify_goal：基于确定性的 GoalSpec 判定目标是否达成，与规划器解耦，
      不触发任何 planner.plan()（对 LLMPlanner 尤为重要）。
恢复的具体编排（重试次数、重规划）由 AgentRuntime 依据 max_retries/max_replans 驱动。
"""

from __future__ import annotations

from typing import Mapping

from robot_agent.core.types import SkillResult
from robot_agent.planning.goal import GoalSpec
from robot_agent.skills.base import Skill
from robot_agent.world.state import WorldState


class ExecutionMonitor:
    """执行结果监控与目标校验。"""

    def check(
        self,
        result: SkillResult,
        skill: Skill,
        before: WorldState,
        after: WorldState,
        params: Mapping[str, object],
    ) -> bool:
        """单步是否达标：结果成功且执行前后状态满足技能后置条件。"""
        return result.ok and skill.postconditions(before, after, params, result)

    def verify_goal(self, goal: GoalSpec, world: WorldState) -> bool:
        """目标是否已闭环达成（对当前世界的确定性判定）。"""
        return goal.is_satisfied(world)
