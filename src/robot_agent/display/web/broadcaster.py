"""线程安全的事件广播器。

运行时线程 publish 事件，多个 SSE 连接各自持有一个队列消费。新连接订阅时会先
收到历史事件（回放），从而无论何时打开浏览器都能看到完整闭环。
"""

from __future__ import annotations

import queue
import threading
from typing import Any


class EventBroadcaster:
    """一对多事件分发：一个生产者，多个 SSE 消费者。"""

    def __init__(self, keep_history: bool = True) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[dict[str, Any]]] = []
        self._history: list[dict[str, Any]] = []
        self._keep_history = keep_history

    def publish(self, payload: dict[str, Any]) -> None:
        """广播一条事件到所有订阅者，并按需记入历史。"""
        with self._lock:
            if self._keep_history:
                self._history.append(payload)
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(payload)

    def subscribe(self) -> "queue.Queue[dict[str, Any]]":
        """新增一个订阅队列，并先灌入历史事件供回放。"""
        q: "queue.Queue[dict[str, Any]]" = queue.Queue()
        with self._lock:
            for item in self._history:
                q.put(item)
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue[dict[str, Any]]") -> None:
        """移除订阅队列（连接关闭时调用）。"""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def history(self) -> list[dict[str, Any]]:
        """返回历史事件副本。"""
        with self._lock:
            return list(self._history)

    def latest(self) -> dict[str, Any] | None:
        """返回最近一条事件（供 /state 快照）。"""
        with self._lock:
            return self._history[-1] if self._history else None

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)
