"""任务调度器（TaskManager）。

将计划的技能调用按 depends_on 依赖关系拓扑排序为线性执行序列，支持多步协同
（顺序 + 依赖）。原型采用依赖感知的顺序调度即可满足 pick-and-place 类线性任务，
不引入行为树/工作流引擎（YAGNI）；接口保留，未来可替换更复杂的调度策略。
"""

from __future__ import annotations

from robot_agent.core.errors import SchedulingError
from robot_agent.planning.base import Plan, PlanStep
from robot_agent.planning.dependency_graph import topological_order


class TaskManager:
    """基于拓扑排序的计划调度器。"""

    def schedule(self, plan: Plan) -> list[PlanStep]:
        """把计划展开为可顺序执行的步骤列表。

        使用 Kahn 算法做拓扑排序；发现非法依赖或循环依赖时抛 SchedulingError。
        同层就绪节点按原始下标升序出队，保证结果确定可复现。
        """
        order = topological_order(plan.steps, _dependency_error)
        return [plan.steps[index] for index in order]


def _dependency_error(step_id: str, dependency: str) -> SchedulingError:
    return SchedulingError(f"步骤 {step_id} 存在非法依赖：{dependency}")
