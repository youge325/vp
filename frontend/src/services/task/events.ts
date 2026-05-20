// pure: no Vue / no Pinia / no Tauri
// 任务事件 reducer — 把 IPC payload 应用到 MediaTaskState。
//
// Phase 16 — ``MediaTaskState.error`` 字段移除,reducer 不再写 error。
// 错误展示统一走 [[useIssueStore]] 的 ``'task'`` scope:终态 reducer
// (``applyTaskError`` / ``applyTaskCancelled``)只负责 status / timestamps,
// banner 由 [[finalize.ts]] ``handleErrored`` 与 [[batch/events.ts]]
// ``onCancelled`` 通过 ``deps.setTaskIssue`` 写入。
//
// ``applyTaskCancelled`` 不再接 payload —— payload 对 reducer 的可见影响
// 只是 error 的 message/details,而 error 已经搬到 issueStore,reducer
// 本身不需要 payload 信息。caller(``onCancelled``)拿到 payload 后自己
// 构造 banner。

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
    percent: 0,
    current: 0,
    total: 0,
    stage: '',
    stageIndex: 0,
    stageTotal: 0,
    logs: [],
    outputPath: '',
    processedFrames: 0,
    timeSeconds: 0,
    startedAt: null,
    finishedAt: null,
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

export function applyTaskProgress(state: MediaTaskState, payload: TaskProgressPayload): MediaTaskState {
  const status = state.status === 'paused' || state.status === 'cancelling' ? state.status : 'running'

  return {
    ...state,
    status,
    percent: payload.percent ?? state.percent,
    current: payload.current ?? state.current,
    total: payload.total ?? state.total,
    stage: payload.stage ?? state.stage,
    stageIndex: payload.stageIndex ?? state.stageIndex,
    stageTotal: payload.stageTotal ?? state.stageTotal,
    startedAt: state.startedAt ?? new Date().toISOString(),
  }
}

export function applyTaskPaused(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'paused',
    startedAt: state.startedAt ?? new Date().toISOString(),
  }
}

export function applyTaskResumed(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'running',
    startedAt: state.startedAt ?? new Date().toISOString(),
  }
}

export function applyTaskCancelling(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'cancelling',
  }
}

export function applyTaskCompleted(state: MediaTaskState, payload: TaskCompletedPayload): MediaTaskState {
  return {
    ...state,
    status: 'completed',
    percent: 100,
    outputPath: payload.outputPath ?? state.outputPath,
    processedFrames: payload.processedFrames ?? state.processedFrames,
    timeSeconds: payload.timeSeconds ?? state.timeSeconds,
    finishedAt: new Date().toISOString(),
  }
}

export function applyTaskError(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'error',
    finishedAt: new Date().toISOString(),
  }
}

export function applyTaskCancelled(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'cancelled',
    finishedAt: new Date().toISOString(),
  }
}

export function applyTaskResumeStatus(state: MediaTaskState, payload: ResumeStatus): MediaTaskState {
  return {
    ...state,
    resumeStatus: { ...payload },
  }
}
