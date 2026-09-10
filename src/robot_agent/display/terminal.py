"""终端实时可视化上位机（只读监控）。

订阅 RuntimeEvent，把网格世界与任务/步骤/恢复状态实时渲染到终端。零依赖
（仅用标准库与 ANSI 转义）。渲染逻辑抽成纯函数 render_frame 便于单测；
TerminalMonitor 只负责清屏、输出与节流。

图例：R=机器人  *=可抓取物  #=容器  o=其它实体  .=空格
"""

from __future__ import annotations

import sys
import time
from typing import TextIO

from robot_agent.runtime.events import RuntimeEvent
from robot_agent.world.state import WorldState

_KIND_LABEL = {
    "task_started": "任务开始",
    "step_result": "步骤执行",
    "replan": "重规划",
    "task_finished": "任务结束",
}

_CLEAR_HOME = "\x1b[2J\x1b[H"  # 清屏并将光标移到左上角


def _grid_size(world: WorldState) -> tuple[int, int]:
    """由世界中的坐标推断渲染网格尺寸（无需依赖仿真器边界）。"""
    poses = [info.pose for info in world.objects.values()] + [world.robot_pose]
    width = max((p.x for p in poses), default=0) + 1
    height = max((p.y for p in poses), default=0) + 1
    return width, height


def _cell_symbol(world: WorldState, x: int, y: int) -> str:
    """单元格符号，按 机器人 > 可抓取 > 容器 > 其它 的优先级。"""
    if world.robot_pose.x == x and world.robot_pose.y == y:
        return "R"
    infos = [
        info
        for info in world.objects.values()
        if info.pose.x == x and info.pose.y == y
    ]
    if not infos:
        return "."
    if any(i.is_graspable for i in infos):
        return "*"
    if any(i.is_container for i in infos):
        return "#"
    return "o"


def render_frame(event: RuntimeEvent) -> str:
    """把一个运行时事件渲染为可打印的文本帧（纯函数，无副作用）。"""
    world = event.world
    width, height = _grid_size(world)

    lines: list[str] = []
    lines.append("┌─ 上位机监控 ────────────────────────────")
    lines.append(f"│ 目标：{event.goal or '-'}")
    lines.append(f"│ 事件：{_KIND_LABEL.get(event.kind, event.kind)}")
    if event.task is not None:
        status = event.task.status.value
        err = f"（{event.task.error}）" if event.task.error else ""
        lines.append(f"│ 任务状态：{status}{err}")
    if event.step is not None:
        icon = "✅" if event.step.status == "ok" else "❌"
        retry = f" [重试#{event.step.attempt}]" if event.step.attempt > 0 else ""
        lines.append(f"│ 当前步骤：{icon} {event.step.skill}{retry} — {event.step.message}")
    if event.kind == "replan":
        lines.append(f"│ 重规划：第 {event.replans} 次 — {event.message}")
    lines.append(f"│ 持有物：{world.holding or '（空）'}")
    lines.append("├─ 世界（左上为原点，x→右，y↓）──────────")

    # 逐行渲染网格
    for y in range(height):
        row = " ".join(_cell_symbol(world, x, y) for x in range(width))
        lines.append(f"│ {row}")

    lines.append("├─ 图例 ─────────────────────────────────")
    lines.append("│ R=机器人  *=可抓取  #=容器  o=其它  .=空")
    lines.append("└────────────────────────────────────────")
    return "\n".join(lines)


class TerminalMonitor:
    """终端实时监控观察者（实现 RuntimeObserver）。"""

    def __init__(
        self,
        step_delay: float = 0.0,
        stream: TextIO | None = None,
        clear: bool = True,
    ) -> None:
        """
        Args:
            step_delay: 每帧停留秒数，便于肉眼观察闭环推进（测试时置 0）。
            stream: 输出流，默认 stdout（测试时可注入 StringIO）。
            clear: 是否每帧清屏刷新（测试时通常置 False）。
        """
        self._step_delay = step_delay
        self._stream = stream if stream is not None else sys.stdout
        self._clear = clear

    def on_event(self, event: RuntimeEvent) -> None:
        frame = render_frame(event)
        if self._clear:
            self._stream.write(_CLEAR_HOME)
        self._stream.write(frame + "\n")
        self._stream.flush()
        if self._step_delay > 0:
            time.sleep(self._step_delay)
