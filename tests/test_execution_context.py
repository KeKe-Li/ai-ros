"""步骤输出引用与执行上下文测试。"""

from __future__ import annotations

import pytest

from robot_agent.core.errors import OutputResolutionError
from robot_agent.planning import OutputRef, ToolCall
from robot_agent.runtime import ExecutionContext


def test_resolve_params_reads_nested_step_output():
    context = ExecutionContext()
    context.record("detect_object", {"objects": [{"id": "red_cube"}]})

    params = context.resolve_params(
        {
            "object_id": OutputRef(
                "detect_object", path=("objects", 0, "id"), expected="red_cube"
            )
        }
    )

    assert params == {"object_id": "red_cube"}


def test_public_plan_types_are_importable():
    call = ToolCall("locate_object", step_id="locate")

    assert call.step_id == "locate"


def test_resolve_params_handles_nested_collections():
    context = ExecutionContext()
    context.record("tool", {"value": 3})

    params = context.resolve_params(
        {
            "items": [
                OutputRef("tool", path=("value",)),
                {"copy": OutputRef("tool", path=("value",))},
            ]
        }
    )

    assert params == {"items": [3, {"copy": 3}]}


def test_resolve_params_rejects_missing_step_output():
    context = ExecutionContext()

    with pytest.raises(OutputResolutionError, match="不存在"):
        context.resolve_params({"value": OutputRef("missing", path=("value",))})


def test_resolve_params_rejects_invalid_path():
    context = ExecutionContext()
    context.record("detect", {"object_ids": []})

    with pytest.raises(OutputResolutionError, match="无法解析"):
        context.resolve_params(
            {"object_id": OutputRef("detect", path=("object_ids", 0))}
        )


def test_resolve_params_rejects_unexpected_value():
    context = ExecutionContext()
    context.record("detect", {"object_ids": ["blue_cube"]})

    with pytest.raises(OutputResolutionError, match="不符合预期"):
        context.resolve_params(
            {
                "object_id": OutputRef(
                    "detect", path=("object_ids", 0), expected="red_cube"
                )
            }
        )
