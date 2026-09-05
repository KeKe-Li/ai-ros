"""规则/mock 任务分解器（默认 Planner）。

面向 pick-and-place 类目标："把 <颜色> <物体> 放到 <容器> 里"。以确定性规则从
目标串解析颜色/容器关键词，再结合当前世界定位目标物与容器，生成技能序列。
无需网络与 API key，保证离线可复现。

具备世界感知的**幂等**特性：根据当前世界只产出"剩余步骤"（如已持有物体则跳过
导航/检测/抓取），因此可安全用于异常恢复时的重规划。
"""

from __future__ import annotations

from robot_agent.core.errors import PlanningError
from robot_agent.planning.base import Plan, Planner, SkillCall
from robot_agent.world.state import WorldState

# 颜色关键词映射（中/英）
_COLOR_KEYWORDS: dict[str, str] = {
    "红": "red",
    "红色": "red",
    "red": "red",
    "蓝": "blue",
    "蓝色": "blue",
    "blue": "blue",
    "绿": "green",
    "绿色": "green",
    "green": "green",
}

# 容器关键词（用于确认目标串确实在描述"放入容器"意图）
_CONTAINER_KEYWORDS: tuple[str, ...] = ("箱", "box", "容器", "筐", "篮", "container")


class MockPlanner(Planner):
    """基于规则的确定性分解器。"""

    def plan(self, goal: str, world: WorldState) -> Plan:
        text = goal.lower()
        color = self._parse_color(text)
        container_id = self._find_container(text, world)
        object_id = self._find_target_object(color, container_id, world)

        # 目标已达成：物体已在容器内
        if world.get(object_id).in_container == container_id:
            return Plan(goal=goal, steps=())

        steps: list[SkillCall] = []

        # 若尚未持有目标物，则需要 导航->检测->抓取
        if world.holding != object_id:
            target_pose = world.objects[object_id].pose
            if world.robot_pose != target_pose:
                steps.append(
                    _linked(steps, SkillCall("navigate", {"target_object": object_id}))
                )
            steps.append(
                _linked(
                    steps,
                    SkillCall(
                        "detect",
                        {"color": color, "graspable": True}
                        if color
                        else {"graspable": True},
                    ),
                )
            )
            steps.append(_linked(steps, SkillCall("grasp", {"object_id": object_id})))

        # 导航到容器并放置
        steps.append(
            _linked(steps, SkillCall("navigate", {"target_object": container_id}))
        )
        steps.append(_linked(steps, SkillCall("place", {"container_id": container_id})))

        return Plan(goal=goal, steps=tuple(steps))

    # --- 解析辅助 ---

    @staticmethod
    def _parse_color(text: str) -> str | None:
        for token, color in _COLOR_KEYWORDS.items():
            if token in text:
                return color
        return None

    @staticmethod
    def _find_container(text: str, world: WorldState) -> str:
        if not any(kw in text for kw in _CONTAINER_KEYWORDS):
            raise PlanningError(f"目标未描述有效的容器/放置意图：{text!r}")
        containers = [
            oid for oid, info in sorted(world.objects.items()) if info.is_container
        ]
        if not containers:
            raise PlanningError("世界中不存在可放置的容器")
        return containers[0]

    @staticmethod
    def _find_target_object(
        color: str | None, container_id: str, world: WorldState
    ) -> str:
        candidates = world.find_objects(color=color, graspable=True)
        # 排除容器自身（理论上容器不可抓取，这里稳妥起见再过滤一次）
        candidates = [c for c in candidates if c != container_id]
        if not candidates:
            raise PlanningError(
                f"世界中找不到匹配的可抓取物体（color={color}）"
            )
        return candidates[0]


def _linked(existing: list[SkillCall], call: SkillCall) -> SkillCall:
    """把 call 线性链接到已有步骤末尾：依赖上一步（若存在）。"""
    if not existing:
        return call
    return SkillCall(call.skill, call.params, depends_on=(len(existing) - 1,))
