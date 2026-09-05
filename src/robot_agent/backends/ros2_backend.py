"""ROS2 执行后端适配器（预留 stub）。

当前 macOS 环境无法运行原生 ROS2，本文件仅定义适配器骨架并文档化各动作与
ROS2 机制的映射关系；部署到 Linux + ROS2 时补全实现即可，上层无需改动。

映射约定：
    navigate_to -> Nav2 的 NavigateToPose action（发送目标位姿，等待 action 结果）
    detect      -> 调用感知节点的 service，或订阅检测结果 topic
    grasp/place -> MoveIt / 自定义机械臂 action（含 TF 坐标变换）
    机器人状态   -> 通过 TF 树与 /joint_states、/odom 等 topic 获取
"""

from __future__ import annotations

from typing import Mapping

from robot_agent.backends.base import RobotBackend
from robot_agent.core.errors import BackendNotAvailableError
from robot_agent.core.types import Pose, SkillResult
from robot_agent.world.state import WorldState

_UNAVAILABLE = (
    "ROS2Backend 尚未在当前环境启用：需要 Linux + ROS2 运行时（rclpy、Nav2、"
    "MoveIt 等）。请在目标部署环境中补全实现，或改用 SimBackend。"
)


class ROS2Backend(RobotBackend):
    """ROS2 适配器骨架。所有动作在未接入真实 ROS2 时抛出明确异常。"""

    def __init__(self, node_name: str = "robot_agent_runtime") -> None:
        self._node_name = node_name

    def navigate_to(
        self, world: WorldState, target: Pose
    ) -> tuple[SkillResult, WorldState]:
        raise BackendNotAvailableError(_UNAVAILABLE)

    def detect(self, world: WorldState, query: Mapping[str, object]) -> SkillResult:
        raise BackendNotAvailableError(_UNAVAILABLE)

    def grasp(self, world: WorldState, object_id: str) -> tuple[SkillResult, WorldState]:
        raise BackendNotAvailableError(_UNAVAILABLE)

    def place(
        self, world: WorldState, container_id: str
    ) -> tuple[SkillResult, WorldState]:
        raise BackendNotAvailableError(_UNAVAILABLE)
