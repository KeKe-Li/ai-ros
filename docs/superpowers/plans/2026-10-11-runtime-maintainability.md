# CLI/Web 生命周期 cleanup 第二批优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有外部行为的前提下，补齐 CLI/Web 生命周期中的 cleanup 契约，确保部分启动失败与执行中异常都能稳定回收 dashboard 资源，并修正启动提示时机。

**Architecture:** 严格基于当前已完成第一轮拆分的真实基线，本批只修改 `src/robot_agent/cli.py` 与 `tests/test_e2e_demo.py`。先用测试锁定部分启动失败、`run_demo()` / `_print_report()` / verbose 输出异常时的 cleanup 语义，再做最小实现，最后跑仓库既有验证矩阵。

**Tech Stack:** Python 3.11+、pytest、ruff、标准库 `argparse` / `threading` / `http.server`。

---

## 文件结构与职责映射

- `src/robot_agent/cli.py`
  - 当前已拥有 dashboard start/stop/wait helper。
  - 本批目标：补齐部分启动失败 cleanup、统一 `_cmd_demo()` 异常 cleanup、修正启动提示时机。
- `tests/test_e2e_demo.py`
  - 当前已覆盖 demo 成功路径与部分 dashboard 生命周期。
  - 本批目标：补部分启动失败、运行期异常 cleanup、verbose 异常 cleanup、启动提示时机测试，以及 `_cmd_demo()` 级别“只 cleanup 一次”的断言。

---

### Task 1: 锁定 `_start_web_dashboard()` 的部分启动失败 cleanup

**Files:**
- Modify: `tests/test_e2e_demo.py`
- Modify: `src/robot_agent/cli.py`

- [ ] **Step 1: 写失败测试，覆盖 server 已启动后 monitor 构造失败**

```python
import pytest
import types


def test_start_web_dashboard_stops_server_when_monitor_init_raises(monkeypatch):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def __init__(self, broadcaster, port):
            self.started = False

        def start(self):
            self.started = True
            calls.append("server.start")

        def stop(self):
            calls.append("server.stop")

    def _boom(*args, **kwargs):
        raise RuntimeError("monitor exploded")

    monkeypatch.setattr(cli, "DashboardServer", _FakeServer)
    monkeypatch.setattr(cli, "WebMonitor", _boom)

    with pytest.raises(RuntimeError, match="monitor exploded"):
        cli._start_web_dashboard(
            types.SimpleNamespace(port=8123, frame_delay=0.1, open=False)
        )

    assert calls == ["server.start", "server.stop"]
```

- [ ] **Step 2: 写失败测试，锁定 monitor 初始化失败时不允许提前打印“已启动”提示**

```python
def test_start_web_dashboard_does_not_print_started_message_when_monitor_init_raises(
    monkeypatch, capsys
):
    from robot_agent import cli
    import pytest
    import types

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def __init__(self, broadcaster, port):
            pass

        def start(self):
            calls.append("server.start")

        def stop(self):
            calls.append("server.stop")

    def _boom(*args, **kwargs):
        raise RuntimeError("monitor exploded")

    monkeypatch.setattr(cli, "DashboardServer", _FakeServer)
    monkeypatch.setattr(cli, "WebMonitor", _boom)

    with pytest.raises(RuntimeError, match="monitor exploded"):
        cli._start_web_dashboard(
            types.SimpleNamespace(port=8123, frame_delay=0.1, open=False)
        )

    out = capsys.readouterr().out
    assert "上位机仪表盘已启动" not in out
    assert calls == ["server.start", "server.stop"]
```
```

- [ ] **Step 3: 单跑这两个新增测试，确认当前实现先失败**

Run:
```bash
./.venv/bin/pytest \
  tests/test_e2e_demo.py::test_start_web_dashboard_stops_server_when_monitor_init_raises \
  tests/test_e2e_demo.py::test_start_web_dashboard_does_not_print_started_message_when_monitor_init_raises \
  -v
```

Expected:
```text
- test_start_web_dashboard_stops_server_when_monitor_init_raises: FAILED
- test_start_web_dashboard_does_not_print_started_message_when_monitor_init_raises: FAILED
- pytest 退出码非 0
```

- [ ] **Step 4: 在 `_start_web_dashboard()` 中实现最小 cleanup，并把提示后移到 monitor 初始化成功之后**

```python
# src/robot_agent/cli.py
server = DashboardServer(...)
server.start()
try:
    web_monitor = WebMonitor(...)
    ...
except Exception:
    server.stop()
    raise
print(f"上位机仪表盘已启动：{server.url}")
return server, web_monitor
```
```

- [ ] **Step 5: 再跑这两个新增测试确认通过**

Run:
```bash
./.venv/bin/pytest \
  tests/test_e2e_demo.py::test_start_web_dashboard_stops_server_when_monitor_init_raises \
  tests/test_e2e_demo.py::test_start_web_dashboard_does_not_print_started_message_when_monitor_init_raises \
  -v
```

Expected:
```text
- 上述 2 个测试全部 PASSED
- pytest 退出码为 0
```

---

### Task 2: 锁定 `_cmd_demo()` 在运行期异常时的统一 cleanup

**Files:**
- Modify: `tests/test_e2e_demo.py`
- Modify: `src/robot_agent/cli.py`

- [ ] **Step 1: 为 `run_demo()` 抛异常写失败测试**

```python
import pytest
import types


def test_cmd_demo_stops_web_resources_when_run_demo_raises(monkeypatch):
    from robot_agent import cli

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    monkeypatch.setattr(
        cli,
        "_start_web_dashboard",
        lambda args: (_FakeServer(), _FakeMonitor()),
    )
    monkeypatch.setattr(
        cli,
        "run_demo",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("demo exploded")),
    )

    with pytest.raises(RuntimeError, match="demo exploded"):
        cli._cmd_demo(
            types.SimpleNamespace(
                planner="mock",
                verbose=False,
                watch=False,
                web=True,
                inject_failure=False,
                frame_delay=0.1,
                port=8123,
                open=False,
                llm_fallback="allow",
            )
        )

    assert calls == ["monitor.stop", "server.stop"]
```

- [ ] **Step 2: 为 `_print_report()` 抛异常写失败测试**

```python
def test_cmd_demo_stops_web_resources_when_print_report_raises(monkeypatch):
    from robot_agent import cli
    import types
    import pytest

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    monkeypatch.setattr(
        cli,
        "_start_web_dashboard",
        lambda args: (_FakeServer(), _FakeMonitor()),
    )
    monkeypatch.setattr(
        cli, "run_demo", lambda **kwargs: types.SimpleNamespace(succeeded=True)
    )
    monkeypatch.setattr(
        cli,
        "_print_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("print exploded")),
    )

    with pytest.raises(RuntimeError, match="print exploded"):
        cli._cmd_demo(
            types.SimpleNamespace(
                planner="mock",
                verbose=False,
                watch=False,
                web=True,
                inject_failure=False,
                frame_delay=0.1,
                port=8123,
                open=False,
                llm_fallback="allow",
            )
        )

    assert calls == ["monitor.stop", "server.stop"]
```

- [ ] **Step 3: 为 verbose 输出抛异常写失败测试**

```python
def test_cmd_demo_stops_web_resources_when_verbose_output_raises(monkeypatch):
    from robot_agent import cli
    import types
    import pytest

    calls = []

    class _FakeServer:
        url = "http://127.0.0.1:8123/"

        def stop(self):
            calls.append("server.stop")

    class _FakeMonitor:
        def stop(self):
            calls.append("monitor.stop")

    class _FakeMemory:
        def episode(self):
            raise RuntimeError("verbose exploded")

    monkeypatch.setattr(
        cli,
        "_start_web_dashboard",
        lambda args: (_FakeServer(), _FakeMonitor()),
    )
    monkeypatch.setattr(cli, "Memory", lambda: _FakeMemory())
    monkeypatch.setattr(
        cli, "run_demo", lambda **kwargs: types.SimpleNamespace(succeeded=True)
    )
    monkeypatch.setattr(cli, "_print_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli, "_wait_for_dashboard_if_needed", lambda *args, **kwargs: None
    )

    with pytest.raises(RuntimeError, match="verbose exploded"):
        cli._cmd_demo(
            types.SimpleNamespace(
                planner="mock",
                verbose=True,
                watch=False,
                web=True,
                inject_failure=False,
                frame_delay=0.1,
                port=8123,
                open=False,
                llm_fallback="allow",
            )
        )

    assert calls == ["monitor.stop", "server.stop"]
```

- [ ] **Step 4: 单跑这三项新增测试，确认当前实现先失败**

Run:
```bash
./.venv/bin/pytest \
  tests/test_e2e_demo.py::test_cmd_demo_stops_web_resources_when_run_demo_raises \
  tests/test_e2e_demo.py::test_cmd_demo_stops_web_resources_when_print_report_raises \
  tests/test_e2e_demo.py::test_cmd_demo_stops_web_resources_when_verbose_output_raises \
  -v
```

Expected:
```text
- test_cmd_demo_stops_web_resources_when_run_demo_raises: FAILED
- test_cmd_demo_stops_web_resources_when_print_report_raises: FAILED
- test_cmd_demo_stops_web_resources_when_verbose_output_raises: FAILED
- pytest 退出码非 0
```

- [ ] **Step 5: 用一处统一 cleanup 路径实现最小修复**

实现归属约束：保留 `_wait_for_dashboard_if_needed()` 负责正常 `--web` 常驻路径的 stop；`_cmd_demo()` 只负责在 `run_demo()` / `_print_report()` / verbose 输出抛异常时做异常路径 cleanup，并通过置空或单一路径避免双重 stop。

```python
# src/robot_agent/cli.py
try:
    report = run_demo(...)
    _print_report(...)
    if memory is not None:
        print(...len(memory.episode()))
    _wait_for_dashboard_if_needed(...)
    return ...
finally:
    ...
```
```

实现要求：
- 正常 `--web` 常驻服务语义不变。
- 异常路径必须释放 monitor/server。
- 不重复 stop 同一资源。

- [ ] **Step 6: 运行 CLI 相关测试确认通过**

Run:
```bash
./.venv/bin/pytest tests/test_e2e_demo.py -v
```

Expected:
```text
- 上述新增 cleanup 测试全部 PASSED
- 现有 dashboard 生命周期相关测试继续 PASSED
- pytest 退出码为 0
```

---

### Task 3: 批次级验证与差异复核

**Files:**
- Modify: `src/robot_agent/cli.py`
- Modify: `tests/test_e2e_demo.py`

- [ ] **Step 1: 复核变更范围只落在 2 个目标文件**

Run:
```bash
git diff --name-only
```

Expected:
```text
只出现：
- src/robot_agent/cli.py
- tests/test_e2e_demo.py
```

- [ ] **Step 2: 运行全量测试**

Run:
```bash
./.venv/bin/pytest -q
```

Expected:
```text
全量通过
```

- [ ] **Step 3: 运行 Ruff lint**

Run:
```bash
./.venv/bin/ruff check .
```

Expected:
```text
All checks passed!
```

- [ ] **Step 4: 运行 Ruff format 检查**

Run:
```bash
./.venv/bin/ruff format --check .
```

Expected:
```text
already formatted
```

- [ ] **Step 5: 复核本批工作区差异**

Run:
```bash
git diff --stat
```

Expected:
```text
仅包含：
- src/robot_agent/cli.py
- tests/test_e2e_demo.py
```

- [ ] **Step 6: 人工验收本批约束**

Expected:
```text
- cleanup 只负责资源回收，不吞掉原始异常
- `demo` 参数、退出码、URL 行为、正常 `--web` 常驻语义不变
- 不出现重复 stop
```

