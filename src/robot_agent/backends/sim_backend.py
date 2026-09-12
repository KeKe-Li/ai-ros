"""纯 Python 仿真后端（默认）。

在 GridWorld 上实现 RobotBackend 的四个动作。每个动作先校验前置条件、
再消费失败注入预算、最后推进世界并返回新的不可变 WorldState。
"""

from __future__ import annotations

from typing import Mapping

from robot_agent.backends.base import RobotBackend
from robot_agent.core.types import Pose, SkillResult
from robot_agent.world.grid_world import GridWorld
from robot_agent.world.state import WorldState


class SimBackend(RobotBackend):
    """基于网格世界的仿真执行后端。"""

    def __init__(self, grid: GridWorld) -> None:
        self._grid = grid

    def navigate_to(
        self, world: WorldState, target: Pose
    ) -> tuple[SkillResult, WorldState]:
        if not self._grid.is_reachable(world.robot_pose, target):
            return SkillResult.failure(f"目标 {target} 不可达"), world
        if self._grid.should_fail("navigate"):
            return SkillResult.failure("导航瞬时故障（注入）"), world
        moved = world.with_robot_pose(target)
        return SkillResult.success(f"已到达 {target}"), moved

    def detect(self, world: WorldState, query: Mapping[str, object]) -> SkillResult:
        color = query.get("color")  # type: ignore[assignment]
        graspable = query.get("graspable")  # type: ignore[assignment]
        object_id = query.get("object_id")
        candidates = world.find_objects(
            color=color,  # type: ignore[arg-type]
            graspable=graspable,  # type: ignore[arg-type]
        )
        if object_id is not None:
            candidates = [oid for oid in candidates if oid == str(object_id)]
        # 仅"看得见"机器人所在位置附近（相邻）的物体
        visible = [
            oid
            for oid in candidates
            if self._grid.is_adjacent(world.robot_pose, world.objects[oid].pose)
        ]
        if self._grid.should_fail("detect"):
            return SkillResult.failure("感知瞬时故障（注入）", object_ids=[])
        if not visible:
            return SkillResult.failure("未检测到匹配物体", object_ids=[])
        return SkillResult.success(f"检测到 {visible}", object_ids=visible)

    def grasp(self, world: WorldState, object_id: str) -> tuple[SkillResult, WorldState]:
        obj = world.get(object_id)
        if obj is None:
            return SkillResult.failure(f"物体不存在：{object_id}"), world
        if not obj.is_graspable:
            return SkillResult.failure(f"物体不可抓取：{object_id}"), world
        if world.holding is not None:
            return SkillResult.failure(f"机械臂已占用：持有 {world.holding}"), world
        if not self._grid.is_adjacent(world.robot_pose, obj.pose):
            return SkillResult.failure("机器人不在物体旁"), world
        if self._grid.should_fail("grasp"):
            return SkillResult.failure("抓取瞬时故障（注入）"), world
        # 抓取成功：持有该物，物体脱离任何容器
        picked = world.with_holding(object_id).with_object(
            object_id, _replace_container(world, object_id, None)
        )
        return SkillResult.success(f"已抓取 {object_id}"), picked

    def place(
        self, world: WorldState, container_id: str
    ) -> tuple[SkillResult, WorldState]:
        if world.holding is None:
            return SkillResult.failure("未持有任何物体，无法放置"), world
        container = world.get(container_id)
        if container is None or not container.is_container:
            return SkillResult.failure(f"目标不是有效容器：{container_id}"), world
        if not self._grid.is_adjacent(world.robot_pose, container.pose):
            return SkillResult.failure("机器人不在容器旁"), world
        if self._grid.should_fail("place"):
            return SkillResult.failure("放置瞬时故障（注入）"), world
        held_id = world.holding
        held = world.get(held_id)
        # 放置成功：物体进入容器并落位到容器坐标，机械臂释放
        placed_obj = _copy_with(held, pose=container.pose, in_container=container_id)
        placed = world.with_object(held_id, placed_obj).with_holding(None)
        return SkillResult.success(f"已将 {held_id} 放入 {container_id}"), placed


def _replace_container(world: WorldState, obj_id: str, container: str | None):
    """返回 obj 的副本，仅修改 in_container 字段。"""
    obj = world.objects[obj_id]
    return _copy_with(obj, in_container=container)


def _copy_with(obj, **changes):
    """ObjectInfo 的不可变更新辅助。"""
    from dataclasses import replace

    return replace(obj, **changes)
