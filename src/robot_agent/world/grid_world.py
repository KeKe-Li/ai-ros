"""纯 Python 网格世界仿真器。

作为默认机器人执行后端的物理基础：提供网格边界、场景构建、几何判定
（是否相邻可交互）以及可选的**失败注入**（用于演示与测试异常恢复）。

设计说明：WorldState 是不可变数据快照，随 Agent 闭环流动；GridWorld 则是有状态的
"仿真设备"，仅持有边界配置与失败注入计数器——这是刻意保留的可变仿真装置，
不属于流经业务逻辑的数据模型。
"""

from __future__ import annotations

from typing import Mapping

from robot_agent.core.types import Pose
from robot_agent.world.state import ObjectInfo, WorldState, build_world


class GridWorld:
    """离散网格仿真器。

    Args:
        width, height: 网格尺寸。
        fail_actions: 失败注入表，形如 {"grasp": 1} 表示 grasp 动作前 1 次返回失败、
            之后成功，用于模拟瞬时故障并验证重试恢复。
    """

    def __init__(
        self,
        width: int,
        height: int,
        fail_actions: Mapping[str, int] | None = None,
    ) -> None:
        self.width = width
        self.height = height
        # 复制为可变计数器，随 should_fail 调用递减
        self._fail_budget: dict[str, int] = dict(fail_actions or {})

    def in_bounds(self, pose: Pose) -> bool:
        """位姿是否在网格边界内。"""
        return 0 <= pose.x < self.width and 0 <= pose.y < self.height

    def is_reachable(self, current: Pose, target: Pose) -> bool:
        """目标是否可达（原型：边界内即可达，路径由曼哈顿步数抽象）。"""
        return self.in_bounds(target)

    def is_adjacent(self, a: Pose, b: Pose) -> bool:
        """两位姿是否相邻或重合（可进行抓取/放置交互的判据）。"""
        return a.manhattan(b) <= 1

    def should_fail(self, action: str) -> bool:
        """消费一次失败注入预算：若该动作仍有失败预算则返回 True 并递减。"""
        budget = self._fail_budget.get(action, 0)
        if budget > 0:
            self._fail_budget[action] = budget - 1
            return True
        return False


def build_pick_and_place_world(
    fail_actions: Mapping[str, int] | None = None,
) -> tuple[GridWorld, WorldState]:
    """构建标准 pick-and-place 演示场景。

    10x10 网格；机器人起点 (0,0)；桌子 table@(5,5) 上有红色方块 red_cube；
    箱子 box@(8,2) 为放置目标。

    Returns:
        (仿真器, 初始世界状态)
    """
    grid = GridWorld(10, 10, fail_actions=fail_actions)
    objects: dict[str, ObjectInfo] = {
        "table": ObjectInfo(pose=Pose(5, 5), color=None),
        "box": ObjectInfo(pose=Pose(8, 2), color="brown", is_container=True),
        "red_cube": ObjectInfo(pose=Pose(5, 5), color="red", is_graspable=True),
    }
    world = build_world(robot_pose=Pose(0, 0), objects=objects)
    return grid, world
