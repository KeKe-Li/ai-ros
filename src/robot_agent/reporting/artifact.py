"""Run artifact 读写。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from robot_agent.core.io import atomic_write_text
from robot_agent.reporting.serializer import (
    diagnostic_to_dict,
    plan_step_to_dict,
    step_record_to_dict,
    world_to_dict,
)
from robot_agent.runtime.agent_runtime import RunReport

_ARTIFACT_VERSION = 1


def build_artifact(
    report: RunReport,
    *,
    scenario: str | None = None,
) -> dict[str, object]:
    return {
        "version": _ARTIFACT_VERSION,
        "goal": report.goal,
        "scenario": scenario,
        "task_status": report.task.status.value,
        "task_error": report.task.error,
        "replans": report.replans,
        "initial_world": world_to_dict(report.initial_world),
        "final_world": world_to_dict(report.world),
        "trace": [step_record_to_dict(item) for item in report.trace],
        "diagnostics": [diagnostic_to_dict(item) for item in report.diagnostics],
        "plan_history": [
            [plan_step_to_dict(step) for step in plan] for plan in report.plan_history
        ],
    }


def save_artifact(
    report: RunReport,
    path: str | Path,
    *,
    scenario: str | None = None,
) -> Path:
    encoded = json.dumps(
        build_artifact(report, scenario=scenario),
        ensure_ascii=False,
        indent=2,
    )
    return atomic_write_text(path, encoded)


def load_artifact(path: str | Path) -> dict[str, Any]:
    artifact_path = Path(path)
    loaded = json.loads(artifact_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("artifact 根结构必须是 JSON 对象")
    return loaded
