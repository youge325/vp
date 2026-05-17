# VP Workbench 开发文档

本文档面向开发者，涵盖 VP Workbench 的总体架构、各层实现细节、通信协议和开发指南。

## 文档导航

| 文档 | 内容 |
|------|------|
| [01. 总体架构概览](01-architecture-overview.md) | 三层架构全景、技术栈、核心设计特征、工作流模块映射 |
| [02. 前端架构](02-frontend-architecture.md) | Vue 3 + Pinia + IPC 层 + 类型生成 + 编译期协议一致性 |
| [03. Rust 桌面外壳架构](03-rust-shell-architecture.md) | Tauri Command、进程管理、任务状态机、持久化、资源解析 |
| [04. Python 后端架构](04-backend-architecture.md) | CLI、流式处理、算法层、FFmpeg 封装、异常体系 |
| [05. IPC 通信协议](05-ipc-protocol.md) | NDJSON 协议、错误码体系、事件分发、跨层契约 |
| [06. 配置数据流](06-data-flow.md) | 参数映射、续传状态、进度上报、四层字段对照表 |
| [07. 任务生命周期](07-task-lifecycle.md) | 状态机、启动/取消/暂停流程、Watchdog、Controller |
| [08. 错误处理](08-error-handling.md) | 三层错误码、跨层传播、编译期一致性保证 |
| [09. 断点续传](09-resume-checkpointing.md) | SegmentManifest、续传决策、片段生命周期、前端 UX |
| [10. 环境与部署](10-environment-deployment.md) | 资源解析、环境变量、Release 构建、CI 工作流 |
| [11. 开发指南](11-development-guide.md) | 开发命令、测试策略、调试技巧、Command/NDJSON 添加 Checklist |

## 阅读建议

- **新加入的开发者**：按编号顺序阅读 01 → 02 → 03 → 04 → 05，建立整体认知后再深入特定主题
- **需要实现新功能**：查阅 11 开发指南中的 Checklist，以及对应架构文档中的源码引用
- **排查跨层问题**：查阅 05 IPC 协议 和 08 错误处理，理解错误传播路径
- **优化性能**：查阅 04 后端架构（三线程流水线）和 07 任务生命周期（Watchdog 配置）

## 架构图索引

所有架构图使用 Mermaid 语法绘制，可在支持 Mermaid 的 Markdown 阅读器（如 GitHub、VS Code）中直接渲染。

| 图表 | 所在文档 |
|------|---------|
| 三层架构全景图 | [01](01-architecture-overview.md) |
| 前端模块依赖图 | [02](02-frontend-architecture.md) |
| 任务状态机（前端） | [02](02-frontend-architecture.md) |
| Rust 模块依赖图 | [03](03-rust-shell-architecture.md) |
| TaskStatePhase 状态机 | [03](03-rust-shell-architecture.md) / [07](07-task-lifecycle.md) |
| Python 包依赖图 | [04](04-backend-architecture.md) |
| 三线程流式流水线 | [04](04-backend-architecture.md) |
| 完整任务执行序列图 | [05](05-ipc-protocol.md) |
| 错误传播双路径序列图 | [05](05-ipc-protocol.md) / [08](08-error-handling.md) |
| 配置数据流图 | [06](06-data-flow.md) |
| 续传决策矩阵图 | [09](09-resume-checkpointing.md) |
