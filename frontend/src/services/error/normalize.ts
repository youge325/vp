// pure: no Vue / no Pinia / no Tauri
// General error normaliser — converts the various shapes Tauri and JS can
// throw into a stable TaskError structure.

import type { TaskError } from '@/types/domain/media'
import { TASK_ERROR_CODES, type TaskErrorCode } from '@/types/protocol/errors'

export function normalizeError(error: unknown, code: TaskErrorCode | string = TASK_ERROR_CODES.ProcessFailed): TaskError {
  if (typeof error === 'object' && error !== null && 'code' in error && 'message' in error) {
    const payload = error as { code?: unknown; message?: unknown; details?: Record<string, unknown> | null }
    return {
      code: typeof payload.code === 'string' ? payload.code : code,
      message: typeof payload.message === 'string' ? payload.message : 'Execution failed.',
      details: payload.details ?? null,
    }
  }

  if (error instanceof Error) {
    return { code, message: error.message, details: null }
  }

  return { code, message: String(error), details: null }
}
