import type {
  MediaTaskState,
  ResumeStatus,
  TaskCompletedPayload,
  TaskError,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types'

export const TERMINAL_PROGRESS_PREFIX = '[VP_PROGRESS]'

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

export function applyTaskCancelled(state: MediaTaskState): MediaTaskState {
  return {
    ...state,
    status: 'cancelled',
    finishedAt: new Date().toISOString(),
    error: {
      code: 'cancelled',
      message: '任务已取消。',
      details: null,
    },
  }
}

export function applyTaskResumeStatus(state: MediaTaskState, payload: ResumeStatus): MediaTaskState {
  return {
    ...state,
    resumeStatus: { ...payload },
  }
}
