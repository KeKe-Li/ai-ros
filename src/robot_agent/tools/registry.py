"""工具注册表与内置信息工具。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from robot_agent.core.types import Pose
from robot_agent.world.state import WorldState


@dataclass(frozen=True)
class Tool:
    """一个可调用的工具：名称 + 描述 + 实现。"""

    name: str
    description: str
    func: Callable[..., Any]


class ToolRegistry:
    """工具注册与调用入口。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, description: str, func: Callable[..., Any]) -> None:
        if name in self._tools:
            raise ValueError(f"工具重复注册：{name}")
        self._tools[name] = Tool(name, description, func)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def describe(self) -> dict[str, str]:
        """返回 名称->描述 映射，供 Planner/Agent 发现可用工具。"""
        return {name: tool.description for name, tool in sorted(self._tools.items())}

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"未注册的工具：{name}")
        return self._tools[name].func(*args, **kwargs)


# --- 内置信息工具（纯只读/计算，不产生物理动作）---


def locate_object(world: WorldState, object_id: str) -> Pose | None:
    """查询物体所在坐标，不存在返回 None。"""
    info = world.get(object_id)
    return info.pose if info else None


def count_objects(world: WorldState, color: str | None = None) -> int:
    """统计世界中（可选按颜色）的物体数量。"""
    if color is None:
        return len(world.objects)
    return len(world.find_objects(color=color))


def estimate_path_cost(world: WorldState, target_id: str) -> int | None:
    """估算机器人到目标实体的曼哈顿步数，目标不存在返回 None。"""
    info = world.get(target_id)
    if info is None:
        return None
    return world.robot_pose.manhattan(info.pose)


def default_tool_registry() -> ToolRegistry:
    """注册全部内置信息工具。"""
    registry = ToolRegistry()
    registry.register("locate_object", "查询物体坐标", locate_object)
    registry.register("count_objects", "按颜色统计物体数量", count_objects)
    registry.register("estimate_path_cost", "估算到目标的步数", estimate_path_cost)
    return registry
