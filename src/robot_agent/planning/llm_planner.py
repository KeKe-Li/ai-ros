"""基于 Claude 的任务分解器（可选能力）。

将目标 + 世界摘要交给 Claude，要求其输出 JSON 计划，再校验为 Plan。
为保证离线/无密钥时仍可运行、可复现，任何失败（未安装 anthropic、无 API key、
网络错误、解析/校验失败）都会**优雅回退**到 MockPlanner，并在 last_source 中标注来源。

模型默认使用 claude-sonnet-5（可在构造时覆盖）。仅在调用 plan() 时才导入
anthropic，避免核心框架产生硬依赖。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass

from robot_agent.core.capabilities import CapabilityKind, CapabilitySpec
from robot_agent.planning.base import (
    OutputRef,
    Plan,
    Planner,
    PlanStep,
    SkillCall,
    ToolCall,
)
from robot_agent.planning.mock_planner import MockPlanner
from robot_agent.world.state import WorldState

_SYSTEM_PREFIX = (
    "你是机器人任务规划器。给定自然语言目标与世界状态，输出把目标分解为技能调用的 JSON。"
    "严格输出 JSON，形如："
    '{"steps":[{"id":"detect_object","skill":"detect",'
    '"params":{"object_id":"red_cube"},"depends_on":[]},'
    '{"id":"grasp_object","skill":"grasp","params":{"object_id":'
    '{"$ref":{"step_id":"detect_object","path":["object_ids",0],'
    '"expected":"red_cube"}}},"depends_on":[0]}]}。'
    "只读工具步骤使用 tool 字段。不要输出解释。"
)


@dataclass(frozen=True)
class PlannerDiagnostic:
    source: str
    stage: str
    error_type: str
    message: str


class LLMPlanner(Planner):
    """调用 Claude 进行任务分解，失败时回退到 MockPlanner。"""

    def __init__(
        self,
        model: str = "claude-sonnet-5",
        max_tokens: int = 1024,
        fallback: Planner | None = None,
        capabilities: Sequence[CapabilitySpec] | None = None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._fallback = fallback or MockPlanner()
        self._capabilities = tuple(capabilities or _default_capabilities())
        self._system = _build_system(self._capabilities)
        self.last_source: str = "unset"  # "llm" 或 "fallback"，供调用方观测
        self.last_diagnostic: PlannerDiagnostic | None = None

    def plan(self, goal: str, world: WorldState) -> Plan:
        try:
            plan = self._plan_via_llm(goal, world)
            self.last_source = "llm"
            self.last_diagnostic = None
            return plan
        except Exception as exc:  # 任何失败都回退，保证可用性与可复现
            self.last_source = "fallback"
            self.last_diagnostic = PlannerDiagnostic(
                source="fallback",
                stage="plan",
                error_type=type(exc).__name__,
                message=str(exc),
            )
            return self._fallback.plan(goal, world)

    # --- 内部实现 ---

    def _plan_via_llm(self, goal: str, world: WorldState) -> Plan:
        import anthropic  # 延迟导入，核心无硬依赖

        client = anthropic.Anthropic()  # 读取 ANTHROPIC_API_KEY
        prompt = f"目标：{goal}\n世界状态：{self._describe_world(world)}"
        response = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=self._system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        )
        return self._parse_plan(goal, text, capabilities=self._capabilities)

    @staticmethod
    def _describe_world(world: WorldState) -> str:
        objs = {
            oid: {
                "pose": [info.pose.x, info.pose.y],
                "color": info.color,
                "graspable": info.is_graspable,
                "container": info.is_container,
                "in_container": info.in_container,
            }
            for oid, info in sorted(world.objects.items())
        }
        return json.dumps(
            {
                "robot_pose": [world.robot_pose.x, world.robot_pose.y],
                "holding": world.holding,
                "objects": objs,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _parse_plan(
        goal: str,
        text: str,
        capabilities: Sequence[CapabilitySpec] | None = None,
    ) -> Plan:
        specs = tuple(capabilities or _default_capabilities())
        allowed_skills = {
            spec.name for spec in specs if spec.kind is CapabilityKind.SKILL
        }
        allowed_tools = {
            spec.name for spec in specs if spec.kind is CapabilityKind.TOOL
        }
        payload = json.loads(_extract_json(text))
        raw_steps = payload["steps"]
        if not isinstance(raw_steps, list):
            raise ValueError("LLM 计划的 steps 必须是列表")
        steps: list[PlanStep] = []
        for index, raw in enumerate(raw_steps):
            if not isinstance(raw, dict):
                raise ValueError(f"LLM 计划步骤 {index} 必须是对象")
            step_id = str(raw.get("id", f"step_{index}"))
            params = _decode_value(raw.get("params", {}))
            if not isinstance(params, dict):
                raise ValueError(f"LLM 计划步骤 {step_id} 的 params 必须是对象")
            depends_on = tuple(int(d) for d in raw.get("depends_on", []))
            if "skill" in raw and "tool" not in raw:
                skill = str(raw["skill"])
                if skill not in allowed_skills:
                    raise ValueError(f"LLM 产出未知技能：{skill}")
                steps.append(SkillCall(skill, params, depends_on, step_id))
            elif "tool" in raw and "skill" not in raw:
                tool = str(raw["tool"])
                if tool not in allowed_tools:
                    raise ValueError(f"LLM 产出未知工具：{tool}")
                steps.append(ToolCall(tool, params, depends_on, step_id))
            else:
                raise ValueError(f"LLM 计划步骤 {step_id} 必须且只能指定 skill 或 tool")
        return Plan(goal=goal, steps=tuple(steps))


def _extract_json(text: str) -> str:
    """从文本中截取首个 JSON 对象（容忍 LLM 附带的多余字符）。"""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("响应中未找到 JSON")
    return text[start : end + 1]


def _decode_value(value: object) -> object:
    """递归解码 LLM JSON 中的结构化输出引用。"""
    if isinstance(value, dict):
        if set(value) == {"$ref"}:
            raw_ref = value["$ref"]
            if not isinstance(raw_ref, dict):
                raise ValueError("$ref 必须是对象")
            raw_path = raw_ref.get("path")
            if not isinstance(raw_path, list) or not all(
                isinstance(part, (str, int)) and not isinstance(part, bool)
                for part in raw_path
            ):
                raise ValueError("$ref.path 必须是由字符串或整数构成的列表")
            return OutputRef(
                step_id=str(raw_ref["step_id"]),
                path=tuple(raw_path),
                expected=raw_ref.get("expected"),
            )
        return {key: _decode_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    return value


def _default_capabilities() -> tuple[CapabilitySpec, ...]:
    """从默认注册表构建 LLM 可用能力，避免维护第二份白名单。"""
    from robot_agent.skills import default_skill_manager
    from robot_agent.tools import default_tool_registry

    return default_skill_manager().specs() + default_tool_registry().specs()


def _build_system(capabilities: Sequence[CapabilitySpec]) -> str:
    lines = [_SYSTEM_PREFIX, "可用能力："]
    for spec in capabilities:
        parameters = ", ".join(
            f"{name}{'' if parameter.required else '?'}"
            for name, parameter in spec.parameters.items()
        )
        lines.append(
            f"- {spec.kind.value}:{spec.name}({parameters}) - {spec.description}"
        )
    return "\n".join(lines)
