# 前端架构

前端基于 Vue 3 Composition API + TypeScript 构建，使用 Pinia 管理全局状态，Vue Router 管理视图路由，Vite 作为构建工具。所有 IPC 相关的 TypeScript 类型由 Rust 层的 `ts-rs` 自动生成，保证前后端 schema 严格一致。

## 技术栈

| 依赖 | 版本 | 用途 |
|------|------|------|
| `vue` | ^3.5.32 | UI 框架，Composition API |
| `vue-router` | ^4.6.3 | 8 个工作流视图路由 |
| `pinia` | ^3.0.3 | 全局状态管理 |
| `@tauri-apps/api` | ^2.10.1 | Tauri IPC 调用与事件监听 |
| `@vicons/ionicons5` | ^0.13.0 | 图标库 |
| `vite` | ^8.0.9 | 构建工具 |
| `vitest` | ^3.2.4 | 单元测试 |

## 目录结构

```
frontend/src/
├── main.ts                 # Vue 应用入口
├── App.vue                 # 根组件（含全局布局）
├── router/
│   └── index.ts            # 8 个视图路由配置
├── stores/
│   ├── env.ts              # 环境检查状态
│   ├── media.ts            # 素材管理
│   ├── preset.ts           # 预设编辑与持久化
│   ├── task.ts             # 批处理队列
│   └── *.spec.ts           # Store 单元测试
├── views/
│   ├── HomeModuleView.vue
│   ├── InputModuleView.vue
│   ├── DecodeModuleView.vue
│   ├── PreprocessModuleView.vue
│   ├── EnhanceModuleView.vue
│   ├── PostprocessModuleView.vue
│   ├── EncodeModuleView.vue
│   └── RenderModuleView.vue
├── components/
│   ├── StepRail.vue        # 左侧导航栏
│   ├── TaskConsole.vue     # 任务日志控制台
│   ├── FilterChainEditor.vue   # 滤镜链编辑器
│   └── ResumeConflictDialog.vue # 续传冲突弹窗
├── lib/
│   ├── tauri.ts            # Tauri invoke 封装
│   ├── workflow.ts         # 工作流定义
│   ├── task-events.ts      # 任务事件状态变换
│   ├── task-mapper.ts      # 配置映射与默认值
│   └── *.spec.ts           # 工具库单元测试
├── types/
│   ├── generated/          # ts-rs 自动生成（~25 个文件）
│   └── index.ts            # 类型补充与扩展
└── assets/                 # 静态资源
```

## Pinia Store 设计

前端采用 4 个 Pinia store，按职责严格分离。每个 store 使用 Vue Composition API 的 `ref`/`reactive`/`computed` 模式定义，而非传统的 Options API。

### env Store（`stores/env.ts`）

**职责**：环境检查结果的缓存、刷新与 GPU 适配器规范化。

**State**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `env.lastCheckedAt` | `string \| null` | 上次检查时间（ISO 字符串） |
| `env.lastProbeAt` | `string \| null` | 上次实际探测时间 |
| `env.checkSource` | `"cache" \| "probe" \| null` | 数据来源 |
| `env.isChecking` | `boolean` | 是否正在检查 |
| `env.checkResult` | `EnvironmentCheckResult \| null` | 检查结果 |
| `env.issue` | `TaskError \| null` | 检查失败错误 |
| `operationIssue` | `OperationIssue \| null` | 当前操作错误 |

**关键 Actions**：

- `recheckEnvironment(forceRefresh)`：调用 Rust `check_environment`，结果通过 `normalizeCheckResult()` 规范化（处理 GPU adapter 的 vendor/deviceType/driverVersion 等字段的兼容性映射）
- `setOperationIssue(scope, error)` / `clearOperationIssue(scope?)`：管理操作级别的错误状态

**Computed**：

- `visibleEncoderProfiles`：从环境检查结果中过滤出可用的编码器配置档

### media Store（`stores/media.ts`）

**职责**：素材列表管理、元数据探测、素材级配置编辑。

**State**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `mediaItems` | `MediaItem[]` | 素材列表 |
| `activeItemId` | `string \| null` | 当前激活编辑的素材 ID |

**MediaItem 结构**：

```typescript
interface MediaItem {
  id: string                    // 时间戳+路径哈希+随机后缀
  inputPath: string
  displayName: string
  selected: boolean             // 是否加入批处理队列
  inspecting: boolean           // 是否正在探测元数据
  info: VideoInfoResult \| null  // 视频元数据（fps、帧数、分辨率等）
  issue: TaskError \| null
  decodeConfig: DecodeConfig    // 素材级解码配置
  workflowConfig: WorkflowConfig
  encodeConfig: EncodeConfig
  outputConfig: OutputConfig
  taskState: MediaTaskState     // 任务执行状态
  lastOutputPath: string
}
```

**关键 Actions**：

- `pickInputs()`：调用 Rust `pick_inputs`，去重后创建 `MediaItem`
- `addMediaPaths(paths, preset?)`：批量添加素材，自动探测元数据
- `inspectMediaItem(id)`：调用 Rust `inspect_video` 获取视频元数据，成功后调用 `normalizeItemProfiles()` 根据视频编码格式匹配合适的解码器
- `setActiveItem(id)`：切换当前编辑的素材
- `normalizeItemProfiles(item)`：根据环境检查结果和视频编码格式，自动校正解码器和编码器配置

**Computed**：

- `activeItem`：当前激活素材
- `selectedItems` / `selectedIds`：已选素材（加入批处理队列的）
- `editor`：当前编辑器的配置来源——若 `activeItem` 存在则用素材级配置，否则用预设配置
- `editingScope`：当前编辑作用域（`"selection"` 或 `"preset"`）

### preset Store（`stores/preset.ts`）

**职责**：工作台预设的编辑、校验、自动保存，以及配置档（Profile）的种子与规范化。

**State**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `draftPreset` | `WorkbenchPreset` | 当前编辑中的预设（响应式） |
| `presetPersistenceReady` | `boolean` | 是否已加载 persisted preset |
| `presetSaveTimer` | `Timeout \| null` | 防抖保存定时器 |

**配置档种子机制**：

当用户切换编码器或解码器配置档时，`seedProfileOptions()` 根据配置档定义自动填充默认选项值：

1. 优先保留用户已设置的值
2. 否则使用配置档定义的 `defaultValue`
3. 否则使用选项的第一个可选值
4. 布尔类型默认 `false`，其他默认空字符串

**关键 Actions**：

- `loadPersistedPreset()`：从 Rust `load_workbench_preset` 加载，失败时回退到 `createDefaultWorkbenchPreset()`
- `persistWorkbenchPreset()`：保存到 Rust，失败静默处理（保证编辑器可用性）
- `schedulePresetSave()`：300ms 防抖自动保存
- `patchDecode(mutator)` / `patchEncode(mutator)` / `patchWorkflow(mutator)` / `patchOutput(mutator)`：不可变更新单段配置，触发自动保存
- `setDecodeProfile(profileName)` / `setEncodeProfile(profileName)`：切换配置档，自动推断 `hwaccel` 和填充选项
- `normalizeDecodeConfig(config, videoCodec)`：根据环境检查结果的可用解码器列表，将配置规范化到有效状态
- `normalizeEncodeConfig(config)`：同上，针对编码器

### task Store（`stores/task.ts`）

**职责**：批处理队列管理、任务生命周期控制、事件监听、续传冲突处理。

**State**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `batch` | `BatchState` | 批处理状态 |
| `batchRuntimeIds` | `string[]` | 本次批处理的素材 ID 列表 |
| `pendingConflict` | `ResumeConflictDescriptor \| null` | 待处理的续传冲突 |
| `detachListenersHandle` | `UnlistenFn \| null` | 事件监听器取消句柄 |

**BatchState 结构**：

```typescript
interface BatchState {
  queue: string[]           // 待处理素材 ID 队列
  currentId: string \| null  // 当前正在处理的素材 ID
  completedCount: number
  failedCount: number
  isRunning: boolean
  isPaused: boolean
  isCancelling: boolean
}
```

**关键 Actions**：

- `startBatch()`：将 `selectedItems` 加入队列，启动批处理
- `runNextQueuedItem()`：出队下一个素材，预检查续传状态，无冲突则启动任务
- `_launchCurrentItem(item, resumeMode?)`：调用 Rust `start_task`
- `_classifyConflict(inspection)`：根据 `inspect-output` 结果判断冲突类型
- `resolveConflict(action)`：处理用户选择的续传策略（fresh/resume/skip/cancel）
- `pauseCurrentTask()` / `resumeCurrentTask()`：暂停/恢复
- `interruptBatch()`：中断批处理（清空队列 + cancelTask）
- `attachTaskListeners()`：注册 6 类 Tauri 事件监听器
- `handleCurrentTaskCompleted()` / `handleCurrentTaskErrored()` / `handleCurrentTaskCancelled()`：任务终止状态处理

**续传冲突处理**：

`task.ts:399-427` 的 `onError` 回调将后端的 `RESUME_CONFLICT` 错误同样转化为 `ResumeConflictDialog`，这样即使预检查通过但运行时文件系统发生变化，用户仍能得到一致的交互体验。

## 工具库分工

> Phase D.5.5 — 本节中提到的 `lib/tauri.ts`、`lib/workflow.ts`、
> `lib/task-events.ts` 已在 Phase C / D 中拆分到更细的命名空间。
> 新路径如下:
> - `lib/tauri.ts` → [`lib/ipc/`](../frontend/src/lib/ipc/)(client.ts /
>   endpoints/{env,media,preset,task}.ts / events.ts)
> - `lib/workflow.ts` → [`config/workbench-modules.ts`](../frontend/src/config/workbench-modules.ts)
>   + [`services/format/labels.ts`](../frontend/src/services/format/labels.ts)
> - `lib/task-events.ts` → [`services/task/events.ts`](../frontend/src/services/task/events.ts)
>
> 下面的 API 列表仍按职责保留,但请按新路径定位文件。

### IPC 调用层(`lib/ipc/`)

[`lib/ipc/client.ts`](../frontend/src/lib/ipc/client.ts) 提供 `safeInvoke()`
封装,所有 endpoint 通过 [`lib/ipc/endpoints/*.ts`](../frontend/src/lib/ipc/endpoints/)
分域:

- **env**:`checkEnvironment()` → `check_environment`
- **media**:`pickInputs()` / `pickOutputDirectory()` / `inspectVideo()` /
  `openOutputLocation()`
- **preset**:`loadWorkbenchPreset()` / `saveWorkbenchPreset()`
- **task**:`startTask()` / `cancelTask()` / `pauseTask()` /
  `resumeTask()` / `checkResume()`

[`lib/ipc/events.ts::listenTaskEvents()`](../frontend/src/lib/ipc/events.ts) 一次
性注册 6 类事件监听器(`onProgress` / `onCompleted` / `onError` /
`onCancelled` / `onLog` / `onResumeStatus`),返回 `UnlistenFn` 批量取消。
Phase D.1.2 起 `onCancelled` 接收 `TaskCancelledPayload { reason }`,前端
通过 `reason === "stalled"` 区分被动取消与用户取消;[Phase D.1.3](data-flow.md)
起 NDJSON 出现"对象但 schema 不匹配"会自动 emit `task-error{SchemaMismatch}`
而非吞掉为 log。

### 静态配置与标签

[`config/workbench-modules.ts`](../frontend/src/config/workbench-modules.ts) 持有
8 个 view 的 `WORKBENCH_MODULES` 数组(key / title / path / description /
icon)。[`services/format/labels.ts`](../frontend/src/services/format/labels.ts)
是 UI 显示标签的集中位置:`WORKFLOW_LABELS` / `PROCESS_ORDER_LABELS` /
`RATE_CONTROL_LABELS` / `RIFE_MODELS` / `VIDEO_EXTENSIONS` /
`CONTAINER_OPTIONS` 等都在这里(未来若引入 vue-i18n,这会是文案收口点)。

### 任务状态机(纯函数)

纯函数集合，负责 `MediaTaskState` 的不可变状态变换。每个函数接收旧状态和事件载荷，返回新状态：

| 函数 | 职责 |
|------|------|
| `createIdleTaskState()` | 创建初始空闲状态 |
| `applyTaskProgress(state, payload)` | 更新进度、阶段、状态为 running |
| `applyTaskPaused(state)` | 状态设为 paused |
| `applyTaskResumed(state)` | 状态设为 running |
| `applyTaskCancelling(state)` | 状态设为 cancelling |
| `applyTaskCompleted(state, payload)` | 状态设为 completed，percent=100 |
| `applyTaskError(state, error)` | 状态设为 error |
| `applyTaskCancelled(state)` | 状态设为 cancelled，附默认错误信息 |
| `applyTaskResumeStatus(state, payload)` | 更新续传状态 |
| `appendTaskLog(state, payload)` | 追加日志，保留最近 300 条，进度行覆盖更新 |

### task-mapper.ts（`lib/task-mapper.ts`）

配置映射、默认预设生成、编码器/解码器选择策略：

| 函数 | 职责 |
|------|------|
| `buildTaskRequest(item, resumeMode?)` | MediaItem → TaskRequest |
| `createDefaultWorkbenchPreset(env)` | 根据环境检查结果生成智能默认预设 |
| `createDefaultDecodeConfig(env, videoCodec)` | 智能选择解码器配置 |
| `createDefaultEncodeConfig(env)` | 智能选择编码器配置（NVIDIA → Intel → CPU） |
| `createDefaultWorkflowConfig()` | 默认工作流配置（补帧 60fps、PyTorch 后端） |
| `createDefaultOutputConfig()` | 默认输出配置 |
| `getVisibleEncoderProfiles()` / `getVisibleDecoderProfiles()` | 过滤可用配置档 |
| `pickPreferredEncoderProfile()` / `pickPreferredDecoderProfile()` | 按优先级选择最佳配置档 |
| `resolvePrimaryMode()` | 根据启用的算法推断主工作流模式 |
| `normalizeCodec()` | 视频编码格式标准化（hevc/h264/av1） |
| `normalizeTaskError()` | 统一错误对象规范化 |
| `clone*Config()` | 深拷贝配置对象 |

## 视图与路由

### 路由配置

[`router/index.ts`](../frontend/src/router/index.ts) 使用 `createWebHashHistory`，共 9 条路由：

| 路由 | 组件 | meta.module |
|------|------|-------------|
| `/` → `/home` | — | — |
| `/home` | `HomeModuleView` | `WORKBENCH_MODULES[0]` |
| `/input` | `InputModuleView` | `WORKBENCH_MODULES[1]` |
| `/decode` | `DecodeModuleView` | `WORKBENCH_MODULES[2]` |
| `/preprocess` | `PreprocessModuleView` | `WORKBENCH_MODULES[3]` |
| `/enhance` | `EnhanceModuleView` | `WORKBENCH_MODULES[4]` |
| `/postprocess` | `PostprocessModuleView` | `WORKBENCH_MODULES[5]` |
| `/encode` | `EncodeModuleView` | `WORKBENCH_MODULES[6]` |
| `/render` | `RenderModuleView` | `WORKBENCH_MODULES[7]` |

每个视图的 `meta.module` 引用 `workflow.ts` 中的模块定义，用于 StepRail 导航栏的高亮和标题渲染。

### 视图职责

| 视图 | 核心职责 |
|------|---------|
| **Home** | 显示环境检查结果摘要、一键重新探测、能力概览卡片 |
| **Input** | 文件导入（拖拽/对话框）、素材列表、元数据展示、全选/删除 |
| **Decode** | 解码模式切换（软件/硬件）、解码器选择、硬件加速设备、选项配置 |
| **Preprocess** | 预处理滤镜链开关、滤镜步骤增删改、参数编辑 |
| **Enhance** | 补帧开关、目标帧率/倍率、模型选择、推理后端/引擎、超分开关、动漫优化开关 |
| **Postprocess** | 后处理滤镜链开关、滤镜步骤增删改、参数编辑 |
| **Encode** | 编码器选择、容器格式、码率控制模式/值、编码选项、输出目录、完成后自动打开 |
| **Render** | 批处理队列状态、进度展示、任务控制台（日志）、暂停/恢复/取消按钮、续传冲突弹窗 |

## 组件分层

### 通用组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **StepRail** | `components/StepRail.vue` | 左侧导航栏，渲染 8 个工作流步骤，高亮当前步骤，支持点击跳转 |
| **TaskConsole** | `components/TaskConsole.vue` | 任务日志控制台，渲染滚动日志列表，支持自动滚动到底部 |
| **FilterChainEditor** | `components/FilterChainEditor.vue` | 滤镜链编辑器，支持增删改滤镜步骤和参数 |
| **ResumeConflictDialog** | `components/ResumeConflictDialog.vue` | 续传冲突弹窗，提供 fresh/resume/skip/cancel 选项 |

### 视图级组件

各 `views/*.vue` 文件为视图级组件，直接消费 Pinia store 的状态和 actions。视图内部可能包含模块级子组件（未在 `components/` 目录中独立提取），这类子组件通常只被单一视图使用。

## 类型生成机制

Rust 层的 [`models.rs`](../frontend/src-tauri/src/models.rs) 是 IPC schema 的唯一可信源。每个数据模型通过 `ts-rs` 的 `#[ts(export, export_to = "../../src/types/generated/")]` 派生宏，在 Rust 编译时自动生成对应的 TypeScript 类型文件。

### 生成示例

Rust 定义：

```rust
#[derive(Debug, Clone, Deserialize, Serialize, JsonSchema, TS)]
#[serde(rename_all = "camelCase")]
#[ts(export, export_to = "../../src/types/generated/")]
pub struct TaskRequest {
    pub input_path: String,
    pub decode_config: DecodeConfig,
    pub workflow_config: WorkflowConfig,
    pub encode_config: EncodeConfig,
    pub output_config: OutputConfig,
    #[serde(default)]
    #[ts(optional)]
    pub resume_mode: Option<String>,
}
```

生成 TypeScript（`types/generated/TaskRequest.ts`）：

```typescript
export type TaskRequest = {
  inputPath: string;
  decodeConfig: DecodeConfig;
  workflowConfig: WorkflowConfig;
  encodeConfig: EncodeConfig;
  outputConfig: OutputConfig;
  resumeMode?: string;
};
```

### 生成的类型文件清单

共 34 个文件，覆盖所有 IPC 数据模型：

**配置模型**：`DecodeConfig.ts`、`WorkflowConfig.ts`、`InterpolationConfig.ts`、`SuperResolutionConfig.ts`、`AnimeConfig.ts`、`PreprocessConfig.ts`、`PostprocessConfig.ts`、`FilterStep.ts`、`EncodeConfig.ts`、`RateControlConfig.ts`、`OutputConfig.ts`、`WorkbenchPreset.ts`

**任务事件载荷**：`TaskRequest.ts`、`TaskProgressPayload.ts`、`TaskCompletedPayload.ts`、`TaskErrorPayload.ts`、`TaskLogPayload.ts`、`ResumeStatusPayload.ts`

**环境检查结果**：`EnvironmentCheckPayload.ts`、`EnvironmentCheckResult.ts`、`FfmpegInfo.ts`、`GpuInfo.ts`、`TensorBackends.ts`、`TensorEngines.ts`、`BackendDeviceSupport.ts`、`OnnxRuntimeInfo.ts`、`OnnxModels.ts`、`RifeModel.ts`、`RuntimeInfo.ts`、`VideoInfo.ts`

**枚举**：`TaskErrorCode.ts`、`TaskEventName.ts`

### 类型扩展

自动生成的类型文件不做手动修改（会被重新生成覆盖）。前端在 `types/index.ts` 中补充额外的应用层类型，如 `MediaItem`、`MediaTaskState`、`BatchState`、`ResumeConflictDescriptor`、`OperationIssue` 等，这些类型不跨越 IPC 边界，纯前端内部使用。
