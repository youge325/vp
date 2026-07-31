import { TASK_ERROR_CODES, type TaskErrorCode, type TaskErrorPayload } from '@/types/protocol'

/**
 * Convert JavaScript, Tauri, and backend error shapes into the shared domain
 * error without depending on a UI, store, service, or IPC adapter.
 */
export function normalizeError(
  error: unknown,
  code: TaskErrorCode = TASK_ERROR_CODES.ProcessFailed,
): TaskErrorPayload {
  if (typeof error === 'object' && error !== null && 'code' in error && 'message' in error) {
    const payload = error as {
      code?: unknown
      message?: unknown
      details?: Record<string, unknown> | null
    }
    return {
      code: typeof payload.code === 'string' ? (payload.code as TaskErrorCode) : code,
      message: typeof payload.message === 'string' ? payload.message : 'Execution failed.',
      details: payload.details ?? null,
    }
  }

  if (error instanceof Error) {
    return { code, message: error.message, details: null }
  }

  return { code, message: String(error), details: null }
}
