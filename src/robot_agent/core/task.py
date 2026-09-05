"""任务数据模型与状态机。

Task 为不可变对象，状态迁移通过返回新副本实现。状态机约束：
    PENDING -> RUNNING -> {SUCCEEDED | FAILED | RECOVERING}
    RECOVERING -> RUNNING（重试/重规划） | FAILED（超出恢复上限）
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


class TaskStatus(str, Enum):
    """任务生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RECOVERING = "recovering"


# 允许的状态迁移表，用于在迁移时快速校验，避免非法状态跳转
_ALLOWED: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.RUNNING}),
    TaskStatus.RUNNING: frozenset(
        {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.RECOVERING}
    ),
    TaskStatus.RECOVERING: frozenset({TaskStatus.RUNNING, TaskStatus.FAILED}),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.FAILED: frozenset(),
}


@dataclass(frozen=True)
class Task:
    """一次任务执行的不可变状态。"""

    goal: str
    status: TaskStatus = TaskStatus.PENDING
    error: str | None = None

    @property
    def is_terminal(self) -> bool:
        """是否处于终态（成功或失败）。"""
        return self.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED)

    def to(self, status: TaskStatus, error: str | None = None) -> "Task":
        """迁移到新状态，返回新副本。

        非法迁移抛出 ValueError，防止状态机被错误驱动。
        """
        if status not in _ALLOWED[self.status]:
            raise ValueError(f"非法状态迁移：{self.status.value} -> {status.value}")
        return replace(self, status=status, error=error)
