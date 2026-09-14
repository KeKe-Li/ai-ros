# 执行数据流与计划安全设计

## 目标

让技能和只读工具的结构化输出可以安全地成为后续步骤输入，并在任何物理动作执行前验证计划的结构、引用、实体和目标一致性。

## 数据模型

- `SkillCall` 增加稳定的 `step_id`。
- 新增 `ToolCall`，与 `SkillCall` 共用 `params`、`depends_on` 和 `step_id` 语义。
- 新增 `OutputRef(step_id, path, expected)`；`path` 用字符串键和整数下标读取上游输出，`expected` 可约束解析值。
- `Plan.steps` 接受 `SkillCall | ToolCall`。本阶段保留现有下标依赖，避免同时改写调度协议。

## 执行上下文

每次计划执行创建独立 `ExecutionContext`。步骤成功后，将 `SkillResult.data` 或工具结果写入对应 `step_id`；下一步执行前递归解析参数中的 `OutputRef`。引用不存在、路径错误或结果不符合 `expected` 时，当前步骤失败且不会调用后端。

重规划后创建新的上下文，避免旧计划的同名步骤输出污染新计划。世界状态仍作为跨计划状态来源。

## 计划验证

新增 `PlanValidator`，在 `TaskManager` 调度前执行：

- 步骤 ID 非空且唯一；
- 技能或工具已经注册；
- 技能必需参数齐全；
- 依赖合法；
- 输出引用只能指向更早且被当前步骤依赖的步骤；
- 导航实体必须存在；
- 抓取对象必须与 `GoalSpec.object_id` 一致；
- 放置容器必须与 `GoalSpec.container_id` 一致；
- 空计划只允许在目标已经满足时出现。

## 感知与工具

规则规划器生成 `detect_object` 步骤，并让 `grasp_object.object_id` 引用检测输出 `object_ids[0]`，同时设置 `expected` 为目标对象。检测后置条件要求结果非空，且指定 `object_id` 时必须出现在结果中。

`AgentRuntime` 可选接收 `ToolRegistry`，执行 `ToolCall` 时把当前世界作为第一个参数传入工具，并把返回值保存为 `{"value": result}`。工具不修改世界。

## 非目标

- 不引入行为树或通用工作流语言。
- 不实现 ROS2Backend。
- 不处理长期 Memory、SSE 背压或深不可变模型。
- 不让 LLM 动态注册工具；只执行调用方显式注册的工具。

