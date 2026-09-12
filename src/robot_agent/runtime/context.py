"""单次计划执行的数据上下文与步骤输出引用解析。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from robot_agent.core.errors import OutputResolutionError
from robot_agent.planning.base import OutputRef


class ExecutionContext:
    """保存成功步骤的输出，并在后续步骤执行前解析参数引用。"""

    def __init__(self) -> None:
        self._outputs: dict[str, dict[str, Any]] = {}

    def record(self, step_id: str, output: Mapping[str, Any]) -> None:
        """记录一个步骤的结构化输出。"""
        self._outputs[step_id] = dict(output)

    def resolve_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        """递归解析参数中的所有 `OutputRef`。"""
        return {key: self._resolve(value) for key, value in params.items()}

    def _resolve(self, value: Any) -> Any:
        if isinstance(value, OutputRef):
            return self._resolve_ref(value)
        if isinstance(value, Mapping):
            return {key: self._resolve(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._resolve(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._resolve(item) for item in value)
        return value

    def _resolve_ref(self, ref: OutputRef) -> Any:
        if ref.step_id not in self._outputs:
            raise OutputResolutionError(f"步骤输出不存在：{ref.step_id}")

        value: Any = self._outputs[ref.step_id]
        try:
            for part in ref.path:
                value = value[part]
        except (KeyError, IndexError, TypeError) as exc:
            raise OutputResolutionError(
                f"无法解析步骤 {ref.step_id} 的输出路径：{ref.path}"
            ) from exc

        if ref.expected is not None and value != ref.expected:
            raise OutputResolutionError(
                f"步骤 {ref.step_id} 的输出 {value!r} 不符合预期 {ref.expected!r}"
            )
        return value
