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

function normalizeInvokeError(error: unknown): Error {
  const message = error instanceof Error ? error.message : String(error)
  if (!isTauriRuntime()) {
    return new Error(BROWSER_RUNTIME_MESSAGE)
  }
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
