import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'
import type {
  EnvironmentCheckResult,
  TaskCompletedPayload,
  TaskError,
  TaskLogPayload,
  TaskProgressPayload,
  TaskRequest,
  VideoInfoResult,
} from '@/types'

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

async function safeInvoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauriRuntime()) {
    throw new Error(BROWSER_RUNTIME_MESSAGE)
  }
  try {
    return await invoke<T>(command, args)
  } catch (error) {
    throw normalizeInvokeError(error)
  }
}

export function pickInputs(): Promise<string[]> {
  return safeInvoke<string[]>('pick_inputs')
}

export function pickOutputDirectory(): Promise<string | null> {
  return safeInvoke<string | null>('pick_output_directory')
}

export function checkEnvironment(): Promise<EnvironmentCheckResult> {
  return safeInvoke<EnvironmentCheckResult>('check_environment')
}

export function inspectVideo(inputPath: string): Promise<VideoInfoResult> {
  return safeInvoke<VideoInfoResult>('inspect_video', { input_path: inputPath })
}

export function startTask(request: TaskRequest): Promise<void> {
  return safeInvoke<void>('start_task', { request })
}

export function cancelTask(): Promise<void> {
  return safeInvoke<void>('cancel_task')
}

export function openOutputLocation(path: string): Promise<void> {
  return safeInvoke<void>('open_output_location', { path })
}

export interface TaskEventHandlers {
  onProgress: (payload: TaskProgressPayload) => void
  onLog: (payload: TaskLogPayload) => void
  onCompleted: (payload: TaskCompletedPayload) => void
  onError: (payload: TaskError) => void
  onCancelled: () => void
}

export async function listenTaskEvents(handlers: TaskEventHandlers): Promise<UnlistenFn> {
  if (!isTauriRuntime()) {
    return () => {
      void handlers
    }
  }

  const unlisteners = await Promise.all([
    listen<TaskProgressPayload>('task-progress', (event) => handlers.onProgress(event.payload)),
    listen<TaskLogPayload>('task-log', (event) => handlers.onLog(event.payload)),
    listen<TaskCompletedPayload>('task-completed', (event) => handlers.onCompleted(event.payload)),
    listen<TaskError>('task-error', (event) => handlers.onError(event.payload)),
    listen('task-cancelled', () => handlers.onCancelled()),
  ])

  return () => {
    for (const unlisten of unlisteners) {
      unlisten()
    }
  }
}
