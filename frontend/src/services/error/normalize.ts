// pure: no Vue / no Pinia / no Tauri
// General error normaliser — converts the various shapes Tauri and JS can
// throw into a stable TaskError structure.
//
// Phase 6a — single source of truth for ``{ code, message, details }``
// extraction. ``lib/ipc/client.ts`` delegates here for ``InvokeError``
// construction; pause/resume/cancel/start error paths in batch
// lifecycle also funnel through this function.
//
// Phase 6b — the return type tightened to ``TaskError`` (= generated
// ``TaskErrorPayload``), and the fallback ``code`` parameter likewise
// narrowed from ``TaskErrorCode | string`` to ``TaskErrorCode`` only.
// Callers that previously passed magic strings like ``'start_failed'``
// must now pass one of the 14 enum values; that cleanup happened in
// Phase 6c. The runtime cast on ``payload.code`` below is safe because
// Phase 4's three-layer drift gate guarantees Rust never sends a code
// outside the union.

import type { TaskError } from '@/types/domain/media'
import { TASK_ERROR_CODES, type TaskErrorCode } from '@/types/protocol'

export function normalizeError(
  error: unknown,
  code: TaskErrorCode = TASK_ERROR_CODES.ProcessFailed,
): TaskError {
  if (typeof error === 'object' && error !== null && 'code' in error && 'message' in error) {
    const payload = error as { code?: unknown; message?: unknown; details?: Record<string, unknown> | null }
    return {
      // Cast is safe: the Phase 4 cross-layer drift gate ensures any
      // ``code`` string we receive from the Rust shell is a member of
      // the ``TaskErrorCode`` union. Anything else is a schema drift
      // bug that should fail the build, not get silently re-typed here.
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
