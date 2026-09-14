"""技能与工具共享的能力、参数、输出和副作用契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from robot_agent.core.frozen import freeze_mapping


class CapabilityKind(StrEnum):
    SKILL = "skill"
    TOOL = "tool"


class SideEffect(StrEnum):
    NONE = "none"
    WORLD = "world"
    EXTERNAL = "external"


@dataclass(frozen=True)
class ParameterSpec:
    accepted_types: tuple[type, ...]
    required: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "accepted_types", tuple(self.accepted_types))

    def accepts(self, value: object) -> bool:
        return isinstance(value, self.accepted_types)


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    kind: CapabilityKind
    description: str
    parameters: Mapping[str, ParameterSpec] = field(default_factory=dict)
    outputs: Mapping[str, ParameterSpec] = field(default_factory=dict)
    side_effect: SideEffect = SideEffect.NONE

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", freeze_mapping(self.parameters))
        object.__setattr__(self, "outputs", freeze_mapping(self.outputs))

    def validate_params(
        self, params: Mapping[str, object], dynamic_types: tuple[type, ...] = ()
    ) -> None:
        unknown = sorted(set(params) - set(self.parameters))
        if unknown:
            raise ValueError(f"能力 {self.name} 包含未知参数：{unknown}")
        missing = sorted(
            name
            for name, spec in self.parameters.items()
            if spec.required and name not in params
        )
        if missing:
            raise ValueError(f"能力 {self.name} 缺少必需参数：{missing}")
        for name, value in params.items():
            if dynamic_types and isinstance(value, dynamic_types):
                continue
            spec = self.parameters[name]
            if not spec.accepts(value):
                expected = ", ".join(item.__name__ for item in spec.accepted_types)
                raise ValueError(
                    f"能力 {self.name} 参数 {name} 类型错误："
                    f"需要 {expected}，实际 {type(value).__name__}"
                )
