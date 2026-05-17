// IPC 协议层 — Tauri invoke 薄封装。
// 不写业务规则,不依赖 stores / composables / views / services。
//
// Phase 6a — 错误规范化逻辑(``{ code, message, details }`` 提取)收敛到
// ``services/error/normalize.ts``,此处只保留 IPC 层特有的两件事:
//   1. ``InvokeError`` Error 子类(callsite 用 ``instanceof`` 判断);
//   2. Tauri "permission denied" / "Command not found" 嗅探(这是 IPC
//      路径才会出现的字符串,与通用错误规范化无关)。

import { invoke } from '@tauri-apps/api/core'

import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'

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

function normalizeInvokeError(error: unknown): Error {
  if (!isTauriRuntime()) {
    return new Error(BROWSER_RUNTIME_MESSAGE)
  }

  // IPC-specific hint surface: when Tauri itself blocks the command
  // (capability ACL miss, freshly added command not in the bundled
  // manifest) it surfaces as a plain ``Error`` whose ``message``
  // contains these substrings. We prepend a developer-facing hint so
  // the in-app banner is actionable without digging through the
  // Rust-side log.
  const rawMessage = error instanceof Error ? error.message : String(error)
  if (rawMessage.includes('not allowed') || rawMessage.includes('Command not found')) {
    return new Error(`${IPC_PERMISSION_MESSAGE}\n${rawMessage}`)
  }

  // Phase 6a — every other shape goes through the canonical
  // ``normalizeError`` so the ``{ code, message, details }`` extraction
  // logic (and its fallback rules) lives in exactly one place.
  const task = normalizeError(error, TASK_ERROR_CODES.ProcessFailed)
  return new InvokeError(task.code, task.message, task.details ?? null)
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
