"""调度器与任务状态机测试。"""

from __future__ import annotations

import pytest

from robot_agent.core.errors import SchedulingError
from robot_agent.core.task import Task, TaskStatus
from robot_agent.planning.base import Plan, SkillCall
from robot_agent.runtime.task_manager import TaskManager


def test_schedule_linear_plan_preserves_order():
    # Arrange
    plan = Plan(
        goal="g",
        steps=(
            SkillCall("a"),
            SkillCall("b", depends_on=(0,)),
            SkillCall("c", depends_on=(1,)),
        ),
    )

    # Act
    order = TaskManager().schedule(plan)

    # Assert
    assert [s.skill for s in order] == ["a", "b", "c"]


def test_schedule_independent_steps_ordered_by_index():
    # Arrange：无依赖的步骤按下标稳定排序
    plan = Plan(goal="g", steps=(SkillCall("x"), SkillCall("y"), SkillCall("z")))

    # Act
    order = TaskManager().schedule(plan)

    # Assert
    assert [s.skill for s in order] == ["x", "y", "z"]


def test_schedule_detects_cycle():
    # Arrange：0->1->0 循环
    plan = Plan(
        goal="g",
        steps=(SkillCall("a", depends_on=(1,)), SkillCall("b", depends_on=(0,))),
    )

    # Act / Assert
    with pytest.raises(SchedulingError):
        TaskManager().schedule(plan)


def test_schedule_rejects_illegal_dependency():
    # Arrange：依赖越界
    plan = Plan(goal="g", steps=(SkillCall("a", depends_on=(5,)),))

    # Act / Assert
    with pytest.raises(SchedulingError):
        TaskManager().schedule(plan)


def test_task_valid_transitions():
    # Arrange / Act
    task = Task("g")
    running = task.to(TaskStatus.RUNNING)
    done = running.to(TaskStatus.SUCCEEDED)

    # Assert：原对象不变，迁移返回新副本
    assert task.status is TaskStatus.PENDING
    assert running.status is TaskStatus.RUNNING
    assert done.status is TaskStatus.SUCCEEDED
    assert done.is_terminal


def test_task_illegal_transition_raises():
    # Arrange
    task = Task("g")

    # Act / Assert：PENDING 不可直接到 SUCCEEDED
    with pytest.raises(ValueError):
        task.to(TaskStatus.SUCCEEDED)


def test_task_recovering_cycle_allowed():
    # Arrange
    running = Task("g").to(TaskStatus.RUNNING)

    # Act
    recovering = running.to(TaskStatus.RECOVERING)
    back = recovering.to(TaskStatus.RUNNING)

    # Assert
    assert back.status is TaskStatus.RUNNING
