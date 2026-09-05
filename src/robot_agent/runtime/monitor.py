"""执行监控与异常恢复策略（ExecutionMonitor）。

职责聚焦于"判断"与"策略"，不负责编排：
    - check：单步执行后是否达标（结果成功且后置条件满足）。
    - verify_goal：复用 Planner 的幂等性——若基于当前世界重新分解得到空计划，
      则认为目标已闭环达成。
恢复的具体编排（重试次数、重规划）由 AgentRuntime 依据 max_retries/max_replans 驱动。
"""

from __future__ import annotations

from typing import Mapping

from robot_agent.core.types import SkillResult
from robot_agent.planning.base import Planner
from robot_agent.skills.base import Skill
from robot_agent.world.state import WorldState


class ExecutionMonitor:
    """执行结果监控与目标校验。"""

    def check(
        self,
        result: SkillResult,
        skill: Skill,
        world: WorldState,
        params: Mapping[str, object],
    ) -> bool:
        """单步是否达标：结果成功且后置条件在新世界中成立。"""
        return result.ok and skill.postconditions(world, params)

    def verify_goal(self, planner: Planner, goal: str, world: WorldState) -> bool:
        """目标是否已闭环达成（重新分解为空计划即视为完成）。"""
        return planner.plan(goal, world).is_empty
