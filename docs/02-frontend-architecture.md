# 前端架构

## 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | ^3.5.32 | 框架与响应式系统 |
| Vite | ^8.0.9 | 构建工具 |
| TypeScript | ~6.0.2 | 类型系统 |
| Pinia | ^3.0.3 | 状态管理 |
| Vue Router | ^4.6.3 | 路由与懒加载 |
| @tauri-apps/api | ^2.10.1 | Tauri 前端 API |
| Vitest | ^3.2.4 | 单元测试 |

## 目录结构与模块依赖

```mermaid
graph TB
    subgraph "视图层"
        V1[views/ 8 个模块视图]
        V2[components/ 通用组件]
    end

    subgraph "组合层"
        C1[composables/app/ 启动 + 编排]
        C2[composables/forms/ 表单逻辑]
        C3[composables/selectors/ 派生状态]
    end

    subgraph "状态层"
        S1[stores/env.ts]
        S2[stores/media.ts]
        S3[stores/preset.ts]
        S4[stores/task.ts]
        S5[stores/issue.ts]
    end

    subgraph "服务层 (纯函数)"
        SV1[services/env/]
        SV2[services/error/]
        SV3[services/format/]
        SV4[services/media/]
        SV5[services/preset/]
        SV6[services/task/]
    end

    subgraph "IPC 层"
        I1[lib/ipc/client.ts]
        I2[lib/ipc/events.ts]
        I3[lib/ipc/endpoints/]
    end

    subgraph "类型层"
        T1[types/domain/]
        T2[types/generated/ ~40 文件]
        T3[types/protocol/]
        T4[types/view/]
    end

    V1 --> C1
    V2 --> C2
    C1 --> S1
    C1 --> S2
    C1 --> S3
    C1 --> S4
    C2 --> S3
    C3 --> S1
    C3 --> S2
    C3 --> S4
    S1 --> SV1
    S2 --> SV4
    S3 --> SV5
    S4 --> SV6
    S5 --> SV2
    SV6 --> I3
    SV1 --> I3
    I3 --> I1
    C1 --> I2
    T3 --> I1
    T3 --> I2
    T2 --> S2
    T2 --> S3
    T2 --> S4
    T1 --> S2
    T1 --> S4
```

## Pinia Store 设计

使用 Composition API 风格（`reactive` + `ref`），共 6 个 store：

| Store | 文件 | 职责 |
|-------|------|------|
| `useEnvStore` | [`stores/env.ts`](../frontend/src/stores/env.ts) | 环境探测状态（是否探测中、探测结果、错误） |
| `useMediaStore` | [`stores/media.ts`](../frontend/src/stores/media.ts) | 媒体列表（增删改查、选中状态、激活项和配置快照） |
| `useMediaRunState` | [`stores/mediaRunState.ts`](../frontend/src/stores/mediaRunState.ts) | 按媒体 ID 保存任务状态和最近输出路径 |
| `usePresetStore` | [`stores/preset.ts`](../frontend/src/stores/preset.ts) | 预设草稿（解码/编码/工作流/输出配置的编辑状态） |
| `useTaskStore` | [`stores/task.ts`](../frontend/src/stores/task.ts) | 批处理任务队列（运行状态、暂停、冲突、进度统计） |
| `useIssueStore` | [`stores/issue.ts`](../frontend/src/stores/issue.ts) | 全局操作错误横幅（按 scope 管理） |

**设计要点：**
- `useMediaStore` 是核心，管理媒体项列表和每个项的配置快照
- `useMediaRunState` 独立保存逐媒体运行状态，避免任务事件写入污染媒体实体
- `useTaskStore` 只管理批处理运行时状态，不直接持有媒体数据
- `useIssueStore` 从 `mediaStore` 中分离出来，避免测试依赖耦合

App 顶栏和 StepRail 通过 `useCurrentTaskStatusLabel()` 读取同一任务状态投影。selector 先用
`useMediaStore.findItem(batch.currentId)` 校验当前媒体，再组合 `useTaskStore` 与
`useMediaRunState`，确保失效的 current ID 不会读取遗留运行状态。

## IPC 调用层

### safeInvoke 与 InvokeError

[`frontend/src/lib/ipc/client.ts`](../frontend/src/lib/ipc/client.ts) 封装所有 Tauri `invoke()` 调用：

```typescript
export type IpcCommand = keyof IpcCommandArgs

export class InvokeError extends Error {
  readonly code: string
  readonly details: Record<string, unknown> | null
  // ...
}

export async function safeInvoke<C extends IpcCommand>(
  command: C,
  ...args: IpcInvokeArgs<C> extends undefined ? [] : [args: IpcInvokeArgs<C>]
): Promise<IpcInvokeResult<C>>
```

- `contract.ts` 集中声明 11 个命令的参数与返回类型，endpoint 调用按命令名自动推导
- `isTauriRuntime()` 检测 `window.__TAURI_INTERNALS__`，区分桌面运行和浏览器预览模式
- `normalizeInvokeError()` 处理 Rust 序列化的 `{ code, message }`，包装为 `InvokeError`
- Tauri 权限拒绝错误（`not allowed` / `Command not found`）会附加开发者提示

### 按领域分组的端点

[`frontend/src/lib/ipc/endpoints/`](../frontend/src/lib/ipc/endpoints/) 按业务领域组织：

| 文件 | 职责 |
|------|------|
| `env.ts` | `check_environment` |
| `media.ts` | `pick_inputs` / `inspect_video` |
| `preset.ts` | `load_workbench_preset` / `save_workbench_preset` / `pick_output_directory` |
| `task.ts` | `start_task` / `cancel_task` / `control_task`（`kind: "pause" | "resume"`）/ `check_resume_state` / `open_output_location` |

### 事件监听

[`frontend/src/lib/ipc/events.ts`](../frontend/src/lib/ipc/events.ts) 提供 `listenTaskEvents(handlers)`，订阅 Tauri 推送的任务事件：

| 事件名 | 来源 | 说明 |
|--------|------|------|
| `task-progress` | Rust `protocol.rs` | 进度更新 |
| `task-completed` | Rust `protocol.rs` | 任务完成 |
| `task-error` | Rust `protocol.rs` | 任务错误 |
| `task-cancelled` | Rust `protocol.rs` | 任务取消（区分 User / Stalled） |
| `task-log` | Rust `protocol.rs` | 日志输出 |
| `task-resume-status` | Rust `protocol.rs` | 续传状态 |

事件名定义在 [`frontend/src/types/protocol/events.ts`](../frontend/src/types/protocol/events.ts)，使用 `satisfies` 约束确保覆盖 Rust `TaskEventName` 的所有 variant。

## 任务状态机（纯函数 Reducer）

[`frontend/src/services/task/events.ts`](../frontend/src/services/task/events.ts) 将 IPC payload 映射为 `MediaTaskState` 变换。这是一个纯函数 reducer，不依赖 Vue/Pinia/Tauri：

```mermaid
stateDiagram-v2
    [*] --> idle: createIdleTaskState()
    idle --> running: applyTaskProgress
    running --> paused: applyTaskPaused
    paused --> running: applyTaskResumed
    running --> cancelling: applyTaskCancelling
    cancelling --> cancelled: applyTaskCancelled
    running --> completed: applyTaskCompleted
    running --> error: applyTaskError
    paused --> error: applyTaskError
    cancelling --> error: applyTaskError
```

关键变换函数：
- `applyTaskProgress` — 将空闲任务推进为运行中，不覆盖暂停或取消中状态
- `applyTaskPaused` / `applyTaskResumed` / `applyTaskCancelling` — 更新控制状态
- `applyTaskCompleted` / `applyTaskError` / `applyTaskCancelled` — 仅写入终态
- `appendTaskLog` — 追加日志并折叠连续阶段进度行（保留最近 300 条）
- `applyTaskResumeStatus` — 保存续传进度元数据

## 批处理编排

### BatchRunner 组合模式

[`frontend/src/services/task/batch-runner.ts`](../frontend/src/services/task/batch-runner.ts) 是唯一组合根，直接装配生命周期操作、冲突处理和事件适配：

```mermaid
graph LR
    A[BatchRunner composition root] --> B1[common.ts 状态查询]
    A --> B2[control.ts 暂停/恢复/取消]
    A --> B3[finalize.ts 终态清理]
    A --> B4[queue.ts 任务队列]
    A --> C[conflict.ts 续传冲突]
    A --> D[events.ts NDJSON 适配]
    B3 -. lazy callback .-> B4
    B4 -. lazy callback .-> B3
```

`conflict.ts` 和 `events.ts` 只接收各自需要的 lifecycle capability；内部 queue/finalize 方法不会成为 BatchRunner 的公共返回字段。

`ResumeInspectionResult` 只存在于 IPC 边界。进入任务状态前，`resume-classifier.ts` 将它或运行时 error details 投影为 `{ kind, outputPath, progress }`；对话框不保存输入路径、pipeline kind、sidecar 标记等未消费 wire 字段。

### Task orchestrator runtime 单例

[`frontend/src/composables/app/taskOrchestratorRuntime.ts`](../frontend/src/composables/app/taskOrchestratorRuntime.ts) 缓存 `BatchRunner` 并连接 Pinia、IPC 与事件监听；`useTaskOrchestrator()` 及启动、取消、暂停、恢复、冲突处理路径都取得同一实例。

## 视图与路由

[`frontend/src/router/index.ts`](../frontend/src/router/index.ts) 使用 `createWebHashHistory`，8 个模块视图全部懒加载：

```mermaid
graph LR
    A[App.vue] --> B[StepRail.vue 左侧导航]
    A --> C[IssueBanner.vue 错误横幅]
    A --> D[RouterView 内容区]

    D --> E1[HomeModuleView 环境概览]
    D --> E2[InputModuleView 素材导入]
    D --> E3[DecodeModuleView 解码配置]
    D --> E4[StageModuleView 预处理滤镜]
    D --> E5[EnhanceModuleView 增强算法]
    D --> E6[StageModuleView 后处理滤镜]
    D --> E7[EncodeModuleView 编码配置]
    D --> E8[RenderModuleView 渲染队列]
```

| 视图 | 核心职责 |
|------|---------|
| `HomeModuleView` | 环境探测仪表盘，GPU/FFmpeg 能力概览 |
| `InputModuleView` | 批量导入素材，拖放支持，素材列表管理 |
| `DecodeModuleView` | 解码器配置（硬件加速、解码模式等） |
| `StageModuleView` (`stage=preprocess`) | 预处理滤镜链配置 |
| `EnhanceModuleView` | 超分辨率、补帧算法配置 |
| `StageModuleView` (`stage=postprocess`) | 后处理滤镜链配置 |
| `EncodeModuleView` | 编码器、码率控制、输出格式配置 |
| `RenderModuleView` | 批量渲染控制，输出目录，任务执行 |

## 类型生成机制

### ts-rs 自动生成

Rust 模型在 [`frontend/src-tauri/src/models/`](../frontend/src-tauri/src/models/) 中定义，使用 `#[derive(TS)]` + `#[ts(export)]` 宏。`cargo build` 时自动生成 TypeScript 类型到 `frontend/src/types/generated/`（约 40 个文件）。

示例（[`frontend/src-tauri/src/models/task.rs`](../frontend/src-tauri/src/models/task.rs)）：

```rust
#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskRequest {
    pub input_path: String,
    pub decode_config: DecodeConfig,
    // ...
}
```

### 类型扩展层

生成文件禁止前端代码直接深路径引用。`types/protocol/index.ts` 统一 re-export 所有 generated 类型：

```typescript
export * from '@/types/generated/DecodeConfig'
export * from '@/types/generated/EncodeConfig'
// ... 约 40 个文件
```

前端自定义领域模型在 `types/domain/` 中定义（如 `MediaItem`、`BatchState`、`OperationIssue`），与生成类型互补。

## 编译期协议一致性

这是前端最重要的设计决策之一。通过 TypeScript 类型系统实现零运行时成本的协议覆盖检查：

### 事件名覆盖检查

[`frontend/src/types/protocol/events.ts`](../frontend/src/types/protocol/events.ts):

```typescript
export const TASK_EVENT_NAMES = {
  TaskProgress: 'task-progress',
  TaskCompleted: 'task-completed',
  TaskError: 'task-error',
  TaskCancelled: 'task-cancelled',
  TaskLog: 'task-log',
  TaskResumeStatus: 'task-resume-status',
} as const satisfies Record<string, TaskEventName>

// 编译期校验：必须覆盖所有 variant
type _VariantsCovered = TaskEventName extends _ValuesOf<typeof TASK_EVENT_NAMES> ? true : never
const _COVERAGE_CHECK: _VariantsCovered = true
```

- 若 Rust 新增 `TaskEventName` variant 但未同步到 `TASK_EVENT_NAMES`，`_VariantsCovered` 变为 `never`，`tsc` 报错
- 若 `TASK_EVENT_NAMES` 的值不是合法的 `TaskEventName`（如 typo），`satisfies` 直接报错

### 错误码类型检查

完整错误码集合由 ts-rs 生成的 `TaskErrorCode` union 提供；运行时代码只为实际需要比较或构造的错误码维护别名：

```typescript
export const TASK_ERROR_CODES = {
  ProcessFailed: 'process_failed',
  ResumeConflict: 'resume_conflict',
  IoError: 'io_error',
  SchemaMismatch: 'schema_mismatch',
  PersistenceFailed: 'persistence_failed',
} as const satisfies Record<string, TaskErrorCode>
```

完整性由 Rust/Python/generated TypeScript 三层漂移检查负责；运行时别名表不复制未被前端消费的枚举成员。

### 形状反向锁

[`frontend/src/types/protocol/_contract_check.ts`](../frontend/src/types/protocol/_contract_check.ts) 对核心 IPC 类型做额外的形状校验，防止字段增删导致的类型漂移。
