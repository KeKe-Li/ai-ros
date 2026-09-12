"""运行时事件与观察者接口。

为"边跑边看"的上位机显示提供解耦通道：AgentRuntime 在执行过程中实时发出
结构化事件（RuntimeEvent），任何显示端/记录端只需实现 RuntimeObserver 即可订阅，
与运行时彻底解耦（与 MemorySink 同一依赖倒置思路）。

事件自带世界快照（WorldState 本就是不可变快照），显示端据此渲染，无需回查运行时。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from robot_agent.core.task import Task
from robot_agent.world.state import WorldState


@dataclass(frozen=True)
class StepRecord:
    """单步执行留痕，用于追溯与展示闭环过程。"""

    skill: str
    params: dict[str, object]
    status: str  # "ok" | "failed"
    message: str
    attempt: int
    step_id: str = ""


@dataclass(frozen=True)
class RuntimeEvent:
    """运行时实时事件。

    kind 取值：
        "task_started"  —— 任务开始，携带初始世界与目标。
        "step_result"   —— 单步（含每次重试）执行完成，携带 step 与结果后的世界。
        "replan"        —— 触发一次重规划。
        "task_finished" —— 任务终态（成功/失败）。
    """

    kind: str
    world: WorldState
    goal: str = ""
    task: Task | None = None
    step: StepRecord | None = None
    replans: int = 0
    message: str = ""


class RuntimeObserver(Protocol):
    """运行时事件订阅者接口（可选依赖）。"""

    def on_event(self, event: RuntimeEvent) -> None: ...
