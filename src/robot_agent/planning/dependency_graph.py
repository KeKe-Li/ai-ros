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
    steps: Sequence[PlanStep], error_factory: ErrorFactory[ErrorT]
) -> list[int]:
    """返回稳定的拓扑排序；循环依赖时抛调用方指定异常。"""
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

    if len(order) != len(steps):
        raise _cycle_error(error_factory)
    return order


def _cycle_error(error_factory: ErrorFactory[ErrorT]) -> ErrorT:
    try:
        raise error_factory("", "")
    except Exception as sample:  # noqa: BLE001 - 仅用于保留异常类型，由调用方决定文案
        message = str(sample)
        if "非法依赖" in message:
            if sample.__class__.__name__ == "SchedulingError":
                return sample.__class__("计划存在循环依赖，无法调度")
            return sample.__class__("计划存在循环依赖")
        return sample.__class__("计划存在循环依赖")
