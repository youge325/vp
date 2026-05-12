// IPC 协议层 — Tauri invoke 薄封装。
// 不写业务规则,不依赖 stores / composables / views / services。

import { invoke } from '@tauri-apps/api/core'

const BROWSER_RUNTIME_MESSAGE =
  'Desktop-only commands are unavailable in browser preview. Run `npm run tauri:dev`.'

const IPC_PERMISSION_MESSAGE =
  'The Tauri shell does not currently allow this IPC command. Restart `npm run tauri:dev` or rebuild the app.'

export function isTauriRuntime(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

/**
 * Error thrown by ``safeInvoke`` that preserves the structured ``{ code, message }``
 * envelope produced by the Rust ``ShellError`` serializer. Callers that need to
 * branch on the code (e.g. ``SchemaMismatch`` vs ``PersistenceFailed``) can
 * inspect ``error.code`` directly; callers that only need a message can fall
 * back to the standard ``Error`` API.
 */
export class InvokeError extends Error {
  readonly code: string
  readonly details: Record<string, unknown> | null

  constructor(code: string, message: string, details: Record<string, unknown> | null = null) {
    super(message)
    this.name = 'InvokeError'
    this.code = code
    this.details = details
  }
}

function isShellErrorPayload(value: unknown): value is { code: string; message: string; details?: Record<string, unknown> | null } {
  return (
    typeof value === 'object'
    && value !== null
    && typeof (value as { code?: unknown }).code === 'string'
    && typeof (value as { message?: unknown }).message === 'string'
  )
}

function normalizeInvokeError(error: unknown): Error {
  if (!isTauriRuntime()) {
    return new Error(BROWSER_RUNTIME_MESSAGE)
  }

  if (isShellErrorPayload(error)) {
    return new InvokeError(error.code, error.message, error.details ?? null)
  }

  const message = error instanceof Error ? error.message : String(error)
  if (message.includes('not allowed') || message.includes('Command not found')) {
    return new Error(`${IPC_PERMISSION_MESSAGE}\n${message}`)
  }
  return error instanceof Error ? error : new Error(message)
}

export async function safeInvoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauriRuntime()) {
    throw new Error(BROWSER_RUNTIME_MESSAGE)
  }
  try {
    return await invoke<T>(command, args)
  } catch (error) {
    throw normalizeInvokeError(error)
  }
}
