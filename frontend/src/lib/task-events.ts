import type {
  TaskCompletedPayload,
  TaskError,
  TaskLogPayload,
  TaskProgressPayload,
  TaskRuntimeState,
} from '@/types'

export function createIdleTaskState(): TaskRuntimeState {
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
  }
}

export function appendTaskLog(state: TaskRuntimeState, payload: TaskLogPayload): TaskRuntimeState {
  return {
    ...state,
    logs: [...state.logs, payload.message].slice(-200),
  }
}

export function applyTaskProgress(
  state: TaskRuntimeState,
  payload: TaskProgressPayload,
): TaskRuntimeState {
  return {
    ...state,
    status: 'running',
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

export function applyTaskCompleted(
  state: TaskRuntimeState,
  payload: TaskCompletedPayload,
): TaskRuntimeState {
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

export function applyTaskError(state: TaskRuntimeState, error: TaskError): TaskRuntimeState {
  return {
    ...state,
    status: 'error',
    error,
    finishedAt: new Date().toISOString(),
  }
}

export function applyTaskCancelled(state: TaskRuntimeState): TaskRuntimeState {
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
