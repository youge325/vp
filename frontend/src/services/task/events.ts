// pure: no Vue / no Pinia / no Tauri
// 任务事件 reducer — 把 IPC payload 应用到 MediaTaskState。
//
// Phase 16 — ``MediaTaskState.error`` 字段移除,reducer 不再写 error。
// 错误展示统一走 [[useIssueStore]] 的 ``'task'`` scope。
//
// Phase 17 — ``MediaTaskState`` 11 个 dead 字段移除(percent / current /
// total / stage / stageIndex / stageTotal / processedFrames / timeSeconds /
// outputPath / startedAt / finishedAt)。reducer 现在只动 ``status`` /
// ``logs`` / ``resumeStatus``。payload 的进度数据(``percent`` 等)由
// reducer 接住后直接丢弃 —— 它们的"持久化语义"从来没有 reader,batch
// 粒度的进度条用 ``batch.completedCount / batchTotal``(见 [[TaskConsole.vue]])。
//
// ``applyTaskCancelled`` 不接 payload —— payload 对 reducer 的可见影响
// 只是 error message/details,而 error 已经搬到 issueStore,reducer 本身
// 不需要 payload。caller(``onCancelled``)拿到 payload 后自己构造 banner。

import { TERMINAL_PROGRESS_PREFIX } from '@/types/protocol'
import type {
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types/protocol'
import type { MediaTaskState } from '@/types/domain/media'
import type { ResumeStatus } from '@/types/domain/batch'

export function createIdleTaskState(): MediaTaskState {
  return {
    status: 'idle',
    logs: [],
    resumeStatus: null,
  }
}

export function appendTaskLog(state: MediaTaskState, payload: TaskLogPayload): MediaTaskState {
  const isProgressLine = payload.message.startsWith(TERMINAL_PROGRESS_PREFIX)
  const lastLog = state.logs[state.logs.length - 1] ?? ''

  if (isProgressLine && lastLog.startsWith(TERMINAL_PROGRESS_PREFIX)) {
    return {
      ...state,
      logs: [...state.logs.slice(0, -1), payload.message].slice(-300),
    }
  }

  return {
    ...state,
    logs: [...state.logs, payload.message].slice(-300),
  }
}

export function applyTaskProgress(state: MediaTaskState, _payload: TaskProgressPayload): MediaTaskState {
  // Phase 17 — payload 的 percent / current / total / stage 字段全部丢弃,
  // 视图侧 0 reader。这条 reducer 唯一的作用是把 status 从 idle 拉到
  // running(paused / cancelling 不被覆盖)。
  const status = state.status === 'paused' || state.status === 'cancelling' ? state.status : 'running'
  if (status === state.status) {
    return state
  }
  return { ...state, status }
}

export function applyTaskPaused(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'paused' }
}

export function applyTaskResumed(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'running' }
}

export function applyTaskCancelling(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'cancelling' }
}

export function applyTaskCompleted(state: MediaTaskState, _payload: TaskCompletedPayload): MediaTaskState {
  // Phase 17 — payload.outputPath / processedFrames / timeSeconds 字段丢弃,
  // 视图 0 reader。outputPath 进 ``mediaRunState.lastOutputPath`` 走另一条
  // 写入路径(见 batch/events.ts onCompleted),不再经过 taskState。
  return { ...state, status: 'completed' }
}

export function applyTaskError(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'error' }
}

export function applyTaskCancelled(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'cancelled' }
}

export function applyTaskResumeStatus(state: MediaTaskState, payload: ResumeStatus): MediaTaskState {
  return {
    ...state,
    resumeStatus: { ...payload },
  }
}
