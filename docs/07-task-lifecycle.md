# 任务生命周期与状态机

## 四状态生命周期

[`frontend/src-tauri/src/tasks/state.rs`](../frontend/src-tauri/src/tasks/state.rs) 用一个
`Mutex<TaskStatePhase>` 管理单任务槽：

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Starting: reserve_start()
    Starting --> Running: activate(lease)
    Starting --> Cancelling: cancel 已记录后 activate(lease)
    Starting --> Idle: rollback_start(lease)
    Running --> Cancelling: begin_cancel(reason)
    Running --> Idle: finish_once(lease)
    Cancelling --> Idle: finish_once(lease)
```

| 状态 | 所有权 | 合法行为 |
|------|--------|----------|
| `Idle` | 无 | `reserve_start()` |
| `Starting { lease }` | 启动租约和取消 token | activate、按 lease 回滚、记录首次取消 |
| `Running { lease, handle }` | 租约、控制通道、取消 token | pause、resume、cancel、终结 |
| `Cancelling { lease, handle }` | 同一任务仍持有槽位 | 等待 supervisor 回收并终结 |

`reserve_start()` 在任何命令构建或 spawn 副作用前执行。第二个 start 在 `Starting` 阶段就被拒绝，
不会出现“子进程已创建但任务未登记”的窗口。

## StartLease 规则

每个 `StartLease` 包含单调 id 和该任务唯一的 `CancellationToken`：

- `activate()` 只接受当前 lease，并在 child、pipe 和 root pid 均已取得后发布 `TaskHandle`。
- 任一启动失败都先杀死并回收已创建的进程组，再调用 `rollback_start(lease)`。
- startup 期间到达的 cancel 直接写入 lease token；activate 后状态成为 `Cancelling`。
- `cancel_owned()` 让 watchdog 只能取消自己监管的 lease。
- `finish_once()` 只接受当前运行 lease。回调在状态锁内先提交终态，再把槽位置为 `Idle`；
  过期 supervisor 不能终结新任务，也不能重复发终态。

状态层只返回 `TaskStateError`。`tasks/commands.rs` 是唯一把
`AlreadyRunning / StartLeaseExpired / NoActiveTask / StillStarting / AlreadyCancelling`
映射为 `ShellError` 的命令 adapter。

## 启动流程

```mermaid
sequenceDiagram
    participant UI as Vue
    participant Spawn as spawn_task
    participant State as TaskState
    participant Child as Python process group
    participant Supervisor as TaskSupervisor

    UI->>Spawn: start_task(request)
    Spawn->>State: reserve_start()
    Spawn->>Spawn: build_process_command()
    Spawn->>Child: spawn()
    Spawn->>Spawn: take stdin/stdout/stderr + root pid
    Spawn->>State: activate(lease, control_tx)
    Spawn->>Spawn: start stdout/stderr readers
    Spawn->>Spawn: start bounded stdin writer
    Spawn->>Supervisor: TaskSupervisorSession
    Spawn-->>UI: Ok
```

`command-group` 让 kill 作用于整个进程组；Windows spawn 使用无控制台窗口标志。stdout/stderr
reader 在写入潜在的大 stdin payload 前启动，避免三 pipe 死锁；stdin 写入超时为 10 秒。

## TaskSupervisor 结构化所有权

[`frontend/src-tauri/src/tasks/controller.rs`](../frontend/src-tauri/src/tasks/controller.rs) 的
`TaskSupervisorSession` 一次接管：

- backend child 进程组和 root pid；
- start lease；
- control/output channel；
- stdin writer、stdout reader、stderr reader；
- `StderrCapture`；
- cancellation token；
- progress beat 与 watchdog。

reader 只负责观察和分类，不直接发送终态。supervisor 在同一个 `tokio::select!` 循环中等待
reader 消息、进程退出、取消、暂停/恢复结果、watchdog 和各类 deadline。supervisor 被 abort 或
panic 时，child 的 kill-on-drop owner 仍会终止进程组。

## NDJSON 与终态仲裁

`TerminalState` 保存一个 candidate：

- `Completed(TaskCompletedPayload)`
- `BackendError(TaskErrorPayload)`
- `SupervisorError(TaskErrorPayload)`

仲裁规则：

1. 第一个 supervisor/protocol 错误保持 sticky。
2. 第二个 completed/error envelope 是协议违规，升级为 `schema_mismatch` 并 kill。
3. backend error 原样保留，优先于进程非零 exit status。
4. completed 只有在进程成功退出时有效。
5. 成功退出但无 terminal envelope 是 `schema_mismatch`；非零退出且无 backend error 是
   `runtime_panic`；wait 失败是 `process_failed`。
6. schema mismatch、pipe failure、terminal 后 5 秒仍不退出都会触发进程组 kill。
7. 进程退出后，supervisor 最多等待 5 秒排空 reader，再 join 三个 pipe task；排空或 join 失败
   会覆盖先前 completed。
8. 最终通过 `TaskState.finish_once(lease, emit)` 发送恰好一个事件，然后才释放任务槽。

stderr 使用 400 行/8KB 滚动缓冲。无结构化 backend error 的崩溃会把缓冲写入
`task-error.details.traceback`。

## 取消状态

[`frontend/src-tauri/src/tasks/cancellation.rs`](../frontend/src-tauri/src/tasks/cancellation.rs) 使用
一个 `AtomicU8` 同时表达“未取消 / User / Stalled”，不维护独立布尔值：

```mermaid
stateDiagram-v2
    [*] --> NotCancelled
    NotCancelled --> User: compare_exchange
    NotCancelled --> Stalled: compare_exchange
    User --> User: first reason wins
    Stalled --> Stalled: first reason wins
```

CAS 胜者写入首个原因并通过 `Notify` 唤醒所有 waiter；后续原因不能覆盖它。用户 cancel 在
`TaskState` 锁内同时完成生命周期转换和原因写入，supervisor 观察 token 后终止并回收进程组。
取消原因最终优先于其他 terminal candidate：

- `User` → `task-cancelled { reason: "user" }`
- `Stalled` → `task-cancelled { reason: "stalled", details? }`

## 暂停与恢复

`control_task({ kind: "pause" | "resume" })` 取得当前 task-bound `TaskHandle`，通过容量为 8 的
control channel 发送 `TaskControlMessage`，并等待 typed oneshot reply：

```mermaid
sequenceDiagram
    participant UI as Vue
    participant Command as control_task
    participant Supervisor as TaskSupervisor
    participant Worker as blocking executor
    participant OS as ProcessController

    UI->>Command: pause / resume
    Command->>Supervisor: bounded send + oneshot
    Supervisor->>Worker: spawn_blocking
    Worker->>OS: suspend / resume task root
    OS-->>Worker: typed result
    Worker-->>Supervisor: result
    Supervisor-->>Command: bounded reply
    Command-->>UI: Ok / structured error
```

- command 发送与 reply 各有 5 秒上限；
- supervisor 内 OS 操作有 4 秒上限，保留 1 秒给 reply 传递；
- Windows 使用 task-local 线程枚举/恢复缓存；
- POSIX 使用 `kill(-pgid, SIGSTOP/SIGCONT)`，控制整个进程组；
- OS 扫描在 `spawn_blocking` 执行，取消观察不会被同步系统调用阻塞；
- pause/resume 对 supervisor 当前 pause 状态幂等，取消后拒绝新控制。

## Watchdog

stdout reader 只在收到合法 `progress` envelope 时更新共享 `Instant`。supervisor 默认每 5 秒检查：

- `VP_TASK_STALL_TIMEOUT_SECS` 未设置或非法：600 秒；
- 值为 `0`：禁用；
- 超时：以当前 lease 调用 `cancel_owned(..., Stalled)` 并 kill 进程组。

如果 lease 已失效，watchdog 不能影响新任务。

## 前端控制请求生命周期

前端 `BatchState.controlPending` 保存未决的 `pause | resume | cancel`。每个控制 attempt 记录单调
token 和开始时的 `currentId`；异步回复只有在 token、任务 ID、运行态和 pending kind 仍匹配时
才能提交或回滚。过期回复不会覆盖新任务，也不会清空更新的控制状态。终态 reducer 随后把
`controlPending`、pause/cancelling 标记和当前任务上下文统一清理。

续传冲突的用户选择也使用显式模式：`resume` 重新启动时发送 `force-resume`，`fresh` 发送
`force-fresh`；`skip` 只推进队列，`cancel` 终止批次。不会用默认 `auto` 再次进入同一冲突。
