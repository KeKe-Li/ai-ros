# Runtime 可靠性与工程门禁设计

## 目标

在保持核心零运行时依赖的前提下，统一实体解析和能力契约，建立深不可变执行快照、完整步骤审计、崩溃安全 Memory、有界 SSE，以及可自动执行的工程质量门禁。

## 核心设计

### EntityResolver

实体解析从 `goal.py` 抽离。ASCII/数字/下划线 ID 使用标识符边界匹配，中文名称和别名使用完整别名匹配；多候选必须拒绝。`ObjectInfo` 增加不可变 `aliases`。

### CapabilitySpec

技能与工具共享 `CapabilitySpec`、`ParameterSpec` 和副作用等级。SkillManager、ToolRegistry、PlanValidator 和 LLMPlanner 都从注册能力生成参数校验、允许列表和 prompt，不再维护硬编码白名单。

### 不可变快照与审计

`freeze_value` 递归把映射、列表和集合转为只读结构；`to_jsonable` 负责 Web/Memory 编码。计划参数、技能结果、执行上下文、世界对象和事件字段都在边界处冻结。`StepRecord` 保存步骤类型、原始参数、解析参数、输出和错误类型。

### Memory 与诊断

Memory 先构造候选副本并完成 JSON 编码，再写同目录临时文件，`fsync` 后用 `os.replace` 原子替换，最后更新内存。运行时支持 `BEST_EFFORT` 和 `RAISE` 两种 Memory 失败策略；LLM 回退保留脱敏诊断信息。

### SSE 与工程门禁

EventBroadcaster 使用有界历史和有界订阅队列，慢消费者丢弃最旧事件并累计丢弃计数。增加参数范围校验、Ruff 配置、GitHub Actions、wheel 构建，以及非 editable、非 root Docker 镜像。

## 非目标

- 不实现 ROS2Backend。
- 不改变当前同步执行模型。
- 不引入数据库或第三方消息队列。
- 不在本阶段实现多进程 Memory 文件锁。
