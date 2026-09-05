"""世界状态（WorldState）表示与查询。

WorldState 是流经整个 Agent 闭环的核心数据快照，采用不可变设计：所有更新
（机器人位姿、持有物、物体属性）都返回新副本，杜绝隐藏副作用，便于回溯与调试。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Mapping

from robot_agent.core.types import Pose


@dataclass(frozen=True)
class ObjectInfo:
    """世界中一个实体的静态/动态属性。

    实体既包括可抓取物（如方块），也包括地点/容器（如桌子、箱子）。
    """

    pose: Pose
    color: str | None = None
    is_graspable: bool = False  # 是否可被抓取（如方块）
    is_container: bool = False  # 是否可作为放置目标（如箱子）
    in_container: str | None = None  # 当前所在容器 id（放置后设置）


@dataclass(frozen=True)
class WorldState:
    """某一时刻世界的不可变快照。"""

    robot_pose: Pose
    holding: str | None = None
    objects: Mapping[str, ObjectInfo] = field(default_factory=dict)

    # --- 更新语义：返回新副本 ---

    def with_robot_pose(self, pose: Pose) -> "WorldState":
        """返回机器人移动到新位姿后的世界。"""
        return replace(self, robot_pose=pose)

    def with_holding(self, obj_id: str | None) -> "WorldState":
        """返回机器人持有物变更后的世界。"""
        return replace(self, holding=obj_id)

    def with_object(self, obj_id: str, info: ObjectInfo) -> "WorldState":
        """返回替换/新增某实体后的世界。"""
        new_objects = dict(self.objects)
        new_objects[obj_id] = info
        return replace(self, objects=MappingProxyType(new_objects))

    # --- 查询 ---

    def get(self, obj_id: str) -> ObjectInfo | None:
        """按 id 获取实体，不存在返回 None。"""
        return self.objects.get(obj_id)

    def find_objects(
        self,
        *,
        color: str | None = None,
        graspable: bool | None = None,
        in_container: str | None = None,
    ) -> list[str]:
        """按条件筛选实体 id，返回按 id 排序的稳定列表。"""
        result: list[str] = []
        for obj_id, info in self.objects.items():
            if color is not None and info.color != color:
                continue
            if graspable is not None and info.is_graspable != graspable:
                continue
            if in_container is not None and info.in_container != in_container:
                continue
            result.append(obj_id)
        return sorted(result)


def build_world(robot_pose: Pose, objects: Mapping[str, ObjectInfo]) -> WorldState:
    """构造初始世界的便捷函数，objects 以只读映射封装。"""
    return WorldState(robot_pose=robot_pose, objects=MappingProxyType(dict(objects)))
