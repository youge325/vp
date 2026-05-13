// pure: no Vue / no Pinia / no Tauri
// 任务事件 reducer — 把 IPC payload 应用到 MediaTaskState。

import { TASK_ERROR_CODES, TERMINAL_PROGRESS_PREFIX } from '@/types/protocol'
import type {
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types/protocol'
import type { MediaTaskState, TaskError } from '@/types/domain/media'
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
    error: null,
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
    error: null,
    startedAt: state.startedAt ?? new Date().toISOString(),
  }
}

export function applyTaskPaused(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'paused',
    error: null,
    startedAt: state.startedAt ?? new Date().toISOString(),
  }
}

export function applyTaskResumed(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'running',
    error: null,
    startedAt: state.startedAt ?? new Date().toISOString(),
  }
}

export function applyTaskCancelling(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'cancelling',
    error: null,
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
    error: null,
  }
}

export function applyTaskError(state: MediaTaskState, error: TaskError): MediaTaskState {
  return {
    ...state,
    status: 'error',
    error,
    finishedAt: new Date().toISOString(),
  }
}

export function applyTaskCancelled(
  state: MediaTaskState,
  payload?: TaskCancelledPayload | null,
): MediaTaskState {
  // Phase D.1.2 — stall is now a cancellation with reason "stalled"
  // rather than a synthetic task-error. Reflect that in the error banner:
  // stalled cancels show as ProcessFailed with traceback details; user
  // cancels stay as the friendlier "任务已取消" placeholder.
  const reason = payload?.reason ?? 'user'
  const error: TaskError =
    reason === 'stalled'
      ? {
          code: TASK_ERROR_CODES.ProcessFailed,
          message: '后端进程在配置的超时时间内无任何进度,任务已被中止。',
          details: payload?.details ?? null,
        }
      : {
          code: TASK_ERROR_CODES.Cancelled,
          message: '任务已取消。',
          details: payload?.details ?? null,
        }

  return {
    ...state,
    status: 'cancelled',
    finishedAt: new Date().toISOString(),
    error,
  }
}

export function applyTaskResumeStatus(state: MediaTaskState, payload: ResumeStatus): MediaTaskState {
  return {
    ...state,
    resumeStatus: { ...payload },
  }
}
