// Pure MediaTaskState reducers. Task errors are displayed through issueStore;
// this state retains only status, compacted logs and resume metadata.

import { TERMINAL_PROGRESS_PREFIX, TENSORRT_LOG_PREFIX } from '@/types/protocol'
import type { ResumeStatusPayload, TaskLogPayload } from '@/types/protocol'
import type { MediaTaskState } from '@/types/domain/media'

const escapedProgressPrefix = TERMINAL_PROGRESS_PREFIX.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const STAGE_PROGRESS_KEY_RE = new RegExp(
  `^${escapedProgressPrefix}\\s+\\[(\\d+\\/\\d+\\s+[^\\]]+)\\]`,
)
type TaskLogLineKind = 'progress' | 'tensorrt' | 'default'

function classifyTaskLogLine(line: string): TaskLogLineKind {
  if (line.startsWith(TERMINAL_PROGRESS_PREFIX)) {
    return 'progress'
  }
  if (line.includes(TENSORRT_LOG_PREFIX)) {
    return 'tensorrt'
  }
  return 'default'
}

export function displayTaskLogLine(line: string): string {
  if (classifyTaskLogLine(line) !== 'tensorrt') {
    return line
  }
  const markerIndex = line.indexOf(TENSORRT_LOG_PREFIX)
  if (markerIndex < 0) {
    return line
  }
  return `${line.slice(0, markerIndex)}${line.slice(markerIndex + TENSORRT_LOG_PREFIX.length).trimStart()}`
}

function progressStageKey(line: string): string | null {
  return STAGE_PROGRESS_KEY_RE.exec(line)?.[1] ?? null
}

export function createIdleTaskState(): MediaTaskState {
  return {
    status: 'idle',
    logs: [],
    resumeStatus: null,
  }
}

export function appendTaskLog(state: MediaTaskState, payload: TaskLogPayload): MediaTaskState {
  const isProgressLine = payload.message.startsWith(TERMINAL_PROGRESS_PREFIX)
  const incomingStageKey = isProgressLine ? progressStageKey(payload.message) : null

  if (incomingStageKey) {
    const existingIndex = state.logs.findIndex((line) => progressStageKey(line) === incomingStageKey)
    if (existingIndex >= 0) {
      const logs = state.logs.filter((_, index) => index !== existingIndex)
      return {
        ...state,
        logs: [...logs, payload.message].slice(-300),
      }
    }
    return {
      ...state,
      logs: [...state.logs, payload.message].slice(-300),
    }
  }

  const progressLogs = state.logs.filter((line) => line.startsWith(TERMINAL_PROGRESS_PREFIX))
  if (progressLogs.length > 0) {
    const nonProgressLogs = state.logs.filter((line) => !line.startsWith(TERMINAL_PROGRESS_PREFIX))
    return {
      ...state,
      logs: [...nonProgressLogs, payload.message, ...progressLogs].slice(-300),
    }
  }

  return {
    ...state,
    logs: [...state.logs, payload.message].slice(-300),
  }
}

export function applyTaskProgress(state: MediaTaskState): MediaTaskState {
  // Progress only promotes idle state; paused/cancelling states are preserved.
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

export function applyTaskCompleted(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'completed' }
}

export function applyTaskError(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'error' }
}

export function applyTaskCancelled(state: MediaTaskState): MediaTaskState {
  return { ...state, status: 'cancelled' }
}

export function applyTaskResumeStatus(
  state: MediaTaskState,
  payload: ResumeStatusPayload,
): MediaTaskState {
  return {
    ...state,
    resumeStatus: { ...payload },
  }
}
