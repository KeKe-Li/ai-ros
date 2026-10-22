# CLI/Web 生命周期 cleanup 第二批优化设计

## 背景

`robot-agent` 当前已经具备较完整的闭环能力：目标解析、计划生成、计划校验、调度、执行、重试、重规划、运行时事件广播、Memory 记录、终端/Web 监控都已可工作，并拥有稳定的测试基线。

同时，当前 `feature-dev` 的最新已提交基线已经完成过一轮 runtime/CLI 生命周期收敛，特别是：

- `AgentRuntime` 已拆出 `_start_task`、`_prepare_plan`、`_execute_plan_loop`、`_announce_replan`、`_finalize_task`、`_build_report`
- `StepExecutor` 已拆出 `_build_step_record`、`_remember_attempt`、`_emit_step_result`
- `cli.py` 已拆出 `_start_web_dashboard`、`_stop_web_dashboard`、`_wait_forever`、`_wait_for_dashboard_if_needed`

因此，本轮不再重复“第一轮拆分”本身，而是只讨论当前基线下仍然存在、且适合低风险推进的 **CLI/Web cleanup 缺口**。

---

## 目标

本批只有一个交付目标：

- **补齐 CLI/Web 生命周期中的 cleanup 契约**，确保 dashboard 资源在“部分启动成功后失败”以及“demo 执行/报告输出/verbose 输出过程中抛异常”时仍能稳定回收，并让“已启动”提示只在完整初始化成功后输出。

---

## 非目标

本批明确**不做**以下事项：

- 不重复实现第一轮已经完成的 runtime / CLI helper 拆分。
- 不修改 `AgentRuntime`、`StepExecutor`、`RuntimeHooks`、`RuntimePlanner` 的对外行为。
- 不改变 `failure_kind`、`RunReport`、运行时事件语义。
- 不改变 CLI 的 `demo` 子命令参数、退出码和默认用户路径。
- 不做报告输出通用化。
- 不做大范围目录重组。

---

## 当前真实缺口

### 1. `_start_web_dashboard()` 的部分启动失败 cleanup 还没有被显式锁定

当前启动顺序是：

1. 创建 `EventBroadcaster`
2. 创建 `DashboardServer`
3. `server.start()`
4. 创建 `WebMonitor`
5. 可选 `webbrowser.open()`

如果在 `server.start()` 成功之后，`WebMonitor(...)` 初始化本身抛异常，当前并没有由测试明确锁定“已启动 server 必须立即清理”。

这会带来两类风险：

- 线程/端口资源泄露
- 未来 dashboard 初始化逻辑增加后，失败路径语义继续漂移

### 2. `_cmd_demo()` 的异常路径 cleanup 需要统一化

当前 `cli.py` 已有 `_stop_web_dashboard()` 与 `_wait_for_dashboard_if_needed()`，但资源清理仍主要沿着正常路径收束。

如果未来以下任意一步抛异常：

- `run_demo(...)`
- `_print_report(...)`
- verbose 模式下的额外输出

则 dashboard 资源回收应该由统一 cleanup 路径保证，而不是依赖调用顺序隐含成立。并且 cleanup 只负责资源回收，不改变这些原始异常继续向上冒泡的语义。

### 3. “仪表盘已启动”提示的打印时机当前并不严谨

当前 `cli.py` 在 `server.start()` 成功后就打印“上位机仪表盘已启动”，而 `WebMonitor(...)` 还未完成初始化。

这意味着一旦 monitor 初始化失败，用户可能先看到“已启动”提示，随后流程又进入清理并抛错。这个问题虽然小，但它与“部分启动成功后失败”的生命周期语义是同一个缺口，适合在本批一起收掉。

---

## 设计方案

### 推荐方案：只收敛 `cli.py` + `tests/test_e2e_demo.py`

本批修改范围严格限制为：

- `src/robot_agent/cli.py`
- `tests/test_e2e_demo.py`

不预设 runtime 模块改动；如果实现 CLI/Web cleanup 时发现不可回避的 runtime 问题，应另起补充设计，而不是在本批顺手扩大范围。

### 具体设计原则

1. **部分启动失败必须清理**
   - `DashboardServer.start()` 成功后，只要后续初始化失败，就必须回收 server。
2. **异常路径必须统一 cleanup**
   - `run_demo()`、`_print_report()`、verbose 输出任一环节失败时，都要回收到 monitor/server。
3. **成功提示必须在完整初始化成功后打印**
   - 只有 `DashboardServer` 与 `WebMonitor` 都就绪后，才输出“仪表盘已启动”。
4. **cleanup 不能吞掉原始异常**
   - `run_demo()`、`_print_report()`、verbose 输出失败时，原始异常仍应继续抛出。
5. **正常常驻语义不变**
   - `--web` 下的持续服务模式仍保持现在的用户体验；增强的只是异常路径与初始化边界。

---

## 文件边界

### 预计修改文件

- `src/robot_agent/cli.py`
  - 补齐 dashboard 部分启动失败 cleanup
  - 统一 `_cmd_demo()` 异常路径 cleanup
  - 调整“已启动”提示打印时机
- `tests/test_e2e_demo.py`
  - 补部分启动失败 cleanup 测试
  - 补 `run_demo()` / `_print_report()` / verbose 输出异常 cleanup 测试
  - 视需要补“启动提示只在完整初始化后出现”的测试

### 实施约束

- 继续复用现有 `_start_web_dashboard()`、`_stop_web_dashboard()`、`_wait_for_dashboard_if_needed()` 边界。
- 不为了 cleanup 再引入新的 orchestration 抽象层。
- 不改变正常成功路径的命令行参数、返回码和常驻等待语义。

---

## 兼容性要求

本批必须保持以下兼容点：

- `python -m robot_agent.cli demo` 的参数、退出码和默认行为不变。
- 现有成功路径与 dashboard 等待路径测试继续成立。
- 资源清理增强不能导致重复 stop、额外异常或提示顺序混乱。
- cleanup 不能把原始异常吞掉或改写成新的返回码语义。
- Web dashboard 的 URL 行为不变。

---

## 测试策略

本批采用“小步测试锁定 + 最小实现 + 批次回归”：

1. 先为 `_start_web_dashboard()` 的部分启动失败补测试。
2. 再为 `_cmd_demo()` 在以下场景下的 cleanup 补测试：
   - `run_demo()` 抛异常
   - `_print_report()` 抛异常
   - verbose 输出抛异常
3. 补“启动成功提示只在完整初始化后出现”的测试，并补 monitor 初始化失败时不提前打印成功提示的断言。
4. 实现最小修复。
5. 补 `_cmd_demo()` 级别“只 cleanup 一次”的断言，避免正常常驻路径与异常路径双重 stop。
6. 最后跑批次验证：
   - `./.venv/bin/pytest -q`
   - `./.venv/bin/ruff check .`
   - `./.venv/bin/ruff format --check .`

---

## 风险与控制

### 风险 1：cleanup 补强时误改正常路径

控制方式：
- 保留现有成功路径测试。
- 新测试只聚焦部分启动失败与异常路径 cleanup。

### 风险 2：为了优雅重构而扩大范围

控制方式：
- 本批只允许修改 `cli.py` 与 `tests/test_e2e_demo.py`。
- 超出该范围的结构问题另起设计，不在本批顺手处理。

### 风险 3：只清理资源，不修正提示时机，留下“先报喜后失败”

控制方式：
- 把提示打印时机明确纳入本批范围，并由测试或实现约束锁定。

---

## 推荐实施顺序

1. 补 `_start_web_dashboard()` 部分启动失败 cleanup 测试。
2. 补 `_cmd_demo()` 在 `run_demo()` / `_print_report()` / verbose 输出异常时的 cleanup 测试。
3. 视需要补“已启动”提示时机测试。
4. 在 `cli.py` 中实现最小修复。
5. 跑完整批次验证。

---

## 结论

本批优化应被定义为**第二批、仅聚焦 CLI/Web 生命周期 cleanup 的低风险硬化**。它不再重复第一轮结构拆分，而是把当前仍然缺失的异常路径和初始化边界契约用测试锁住，并以最小改动提升 CLI/Web 的韧性与用户可预期性。
