"""网格渲染与序列化共享的尺寸推断。

终端监控与 Web 仪表盘都需要由世界中的坐标推断最小网格尺寸，公式一致：
宽/高 = max(全部坐标) + 1。集中一处避免两端各留副本、后续漂移。
"""

from __future__ import annotations

from collections.abc import Iterable


def grid_extent(xs: Iterable[int], ys: Iterable[int]) -> tuple[int, int]:
    """返回能容纳所有坐标的最小网格尺寸 (width, height)；坐标为空时回退 (1, 1)。"""
    return max(xs, default=0) + 1, max(ys, default=0) + 1
