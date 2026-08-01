/* Generated from contracts/ipc-manifest.json. Do not edit. */

import type {
  ResumeStatusPayload,
  TaskCancelledPayload,
  TaskCompletedPayload,
  TaskErrorPayload,
  TaskLogPayload,
  TaskProgressPayload,
} from '@/types/generated/contracts'

export const TASK_EVENT_NAMES = {
  TaskProgress: 'task-progress',
  TaskCompleted: 'task-completed',
  TaskError: 'task-error',
  TaskCancelled: 'task-cancelled',
  TaskLog: 'task-log',
  TaskResumeStatus: 'task-resume-status',
} as const

export type TaskEventName = (typeof TASK_EVENT_NAMES)[keyof typeof TASK_EVENT_NAMES]

export interface TaskEventPayloadMap {
  'task-progress': TaskProgressPayload
  'task-completed': TaskCompletedPayload
  'task-error': TaskErrorPayload
  'task-cancelled': TaskCancelledPayload
  'task-log': TaskLogPayload
  'task-resume-status': ResumeStatusPayload
}

export const TERMINAL_PROGRESS_PREFIX = '[VP_PROGRESS]'
export const TENSORRT_LOG_PREFIX = '[VP_TRT]'
