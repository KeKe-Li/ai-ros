"""任务调度器（TaskManager）。

将计划的技能调用按 depends_on 依赖关系拓扑排序为线性执行序列，支持多步协同
（顺序 + 依赖）。原型采用依赖感知的顺序调度即可满足 pick-and-place 类线性任务，
不引入行为树/工作流引擎（YAGNI）；接口保留，未来可替换更复杂的调度策略。
"""

from __future__ import annotations

from robot_agent.core.errors import SchedulingError
from robot_agent.planning.base import Plan, SkillCall


class TaskManager:
    """基于拓扑排序的计划调度器。"""

    def schedule(self, plan: Plan) -> list[SkillCall]:
        """把计划展开为可顺序执行的步骤列表。

        使用 Kahn 算法做拓扑排序；发现非法依赖或循环依赖时抛 SchedulingError。
        同层就绪节点按下标升序出队，保证结果确定可复现。
        """
        steps = plan.steps
        n = len(steps)
        indegree = [0] * n
        adjacency: list[list[int]] = [[] for _ in range(n)]

        for i, step in enumerate(steps):
            for dep in step.depends_on:
                if dep < 0 or dep >= n or dep == i:
                    raise SchedulingError(f"步骤 {i} 存在非法依赖：{dep}")
                adjacency[dep].append(i)
                indegree[i] += 1

        ready = sorted(idx for idx in range(n) if indegree[idx] == 0)
        order: list[int] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for nxt in adjacency[node]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
            ready.sort()

        if len(order) != n:
            raise SchedulingError("计划存在循环依赖，无法调度")
        return [steps[i] for i in order]
