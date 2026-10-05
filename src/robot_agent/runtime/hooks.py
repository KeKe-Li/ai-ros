"""运行时副作用 hooks：Memory、Observer 与结构化诊断。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from robot_agent.runtime.events import RuntimeDiagnostic, RuntimeEvent, RuntimeObserver


class RuntimeHooks:
    """封装运行时的可选副作用通道。"""

    def __init__(
        self,
        *,
        memory: Any = None,
        memory_failure_policy: Any = None,
        observers: Sequence[RuntimeObserver] | None = None,
    ) -> None:
        self._memory = memory
        self._memory_failure_policy = memory_failure_policy
        self._observers = tuple(observers or ())
        self._diagnostics: list[RuntimeDiagnostic] = []

    @property
    def diagnostics(self) -> tuple[RuntimeDiagnostic, ...]:
        return tuple(self._diagnostics)

    def reset(self) -> None:
        self._diagnostics.clear()

    def remember(self, kind: str, **fields: object) -> None:
        if self._memory is None:
            return
        try:
            self._memory.record(kind, **fields)
        except Exception as exc:  # noqa: BLE001 - 行为由显式失败策略决定
            if self._should_raise_memory_failure():
                raise
            self._diagnostics.append(
                RuntimeDiagnostic(
                    component="memory",
                    stage=kind,
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )

    def emit(self, event: RuntimeEvent) -> None:
        """向所有观察者广播事件；单个观察者异常不影响运行时。"""
        for observer in self._observers:
            try:
                observer.on_event(event)
            except Exception as exc:  # noqa: BLE001 - 显示端故障不得拖垮机器人运行
                self._diagnostics.append(
                    RuntimeDiagnostic(
                        component="observer",
                        stage="emit",
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )

    def _should_raise_memory_failure(self) -> bool:
        value = getattr(
            self._memory_failure_policy, "value", self._memory_failure_policy
        )
        return value == "raise"
