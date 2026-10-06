# 2026-10-06 第二轮结构升级执行计划

## 目标

在不改变主闭环行为的前提下，继续提升 runtime 的可诊断性、WebMonitor 的生命周期治理，以及 LLMPlanner 的回退可见性；最后同步 README / README.zh-CN。

## 范围

1. `StepExecutor`：补齐失败分类，让参数解析、skill/tool 调用、后置条件异常、非法步骤类型具备稳定 failure kind。
2. `WebMonitor`：把后台发布线程改成可停止、有限队列、非阻塞丢弃策略，并在 CLI 退出时显式关闭。
3. `LLMPlanner`：增加 `fallback_mode`（`allow` / `strict`），让“允许回退”和“严格失败”成为显式策略；保留结构化诊断。
4. README / README.zh-CN：同步上述行为变化。

## 非目标

- 不改动 ROS2 真接入。
- 不扩展新的技能 / 工具。
- 不在本轮执行 commit / push。

## 实施顺序

1. 先补 RED 测试：
   - `tests/test_runtime_components.py`
   - `tests/test_runtime_exceptions.py`
   - `tests/test_web_display.py`
   - `tests/test_llm_planner.py`
2. 再实现：
   - `runtime/step_executor.py`
   - `runtime/events.py`
   - `display/web/server.py`
   - `cli.py`
   - `planning/llm_planner.py`
3. 最后同步 README 双语文档。

## 验证

- 先跑受影响测试文件，确认从 RED -> GREEN。
- 完成后跑：
  - `python -m pytest -q`
  - `.venv/bin/ruff check .`
  - `.venv/bin/ruff format --check .`

## 风险点

- `StepRecord` 结构新增字段后，需要保证旧测试与序列化兼容。
- `WebMonitor.stop()` 不能让 `on_event()` 重新阻塞，也不能影响无节流模式。
- `LLMPlanner` strict mode 需要与当前 `RuntimePlanner` 的失败包装逻辑兼容。
