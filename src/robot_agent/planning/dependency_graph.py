"""计划依赖图：按 `step_id` 构图、校验与拓扑排序。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from robot_agent.planning.base import PlanStep

ErrorT = TypeVar("ErrorT", bound=Exception)


@dataclass(frozen=True)
class DependencyGraph:
    """计划步骤依赖图。"""

    id_to_index: dict[str, int]
    adjacency: list[list[int]]
    indegree: list[int]


ErrorFactory = Callable[[str, str], ErrorT]
CycleErrorFactory = Callable[[], ErrorT]


def build_dependency_graph(
    steps: Sequence[PlanStep], error_factory: ErrorFactory[ErrorT]
) -> DependencyGraph:
    """按 step_id 构建依赖图；非法依赖时抛调用方指定异常。"""
    size = len(steps)
    id_to_index = {step.step_id: index for index, step in enumerate(steps)}
    adjacency: list[list[int]] = [[] for _ in range(size)]
    indegree = [0] * size

    for index, step in enumerate(steps):
        for dependency in step.depends_on:
            source_index = id_to_index.get(dependency)
            if source_index is None or source_index == index:
                raise error_factory(step.step_id, dependency)
            adjacency[source_index].append(index)
            indegree[index] += 1

    return DependencyGraph(
        id_to_index=id_to_index,
        adjacency=adjacency,
        indegree=indegree,
    )


def topological_order(
    steps: Sequence[PlanStep],
    error_factory: ErrorFactory[ErrorT],
    cycle_error_factory: CycleErrorFactory[ErrorT],
    *,
    graph: DependencyGraph | None = None,
) -> list[int]:
    """返回稳定的拓扑排序；循环依赖时抛 `cycle_error_factory()` 指定的异常。

    调用方可传入已构建的 `graph` 以复用依赖图，避免对同一计划重复构图；
    循环与非法依赖两类错误均由调用方显式提供工厂，本模块保持异常类型无关。
    """
    if graph is None:
        graph = build_dependency_graph(steps, error_factory)
    indegree = list(graph.indegree)
    ready = sorted(index for index, degree in enumerate(indegree) if degree == 0)
    order: list[int] = []

    while ready:
        node = ready.pop(0)
        order.append(node)
        for following in graph.adjacency[node]:
            indegree[following] -= 1
            if indegree[following] == 0:
                ready.append(following)
        ready.sort()

    if len(order) != len(graph.indegree):
        raise cycle_error_factory()
    return order
