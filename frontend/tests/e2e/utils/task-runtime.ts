import type { TauriPage } from './wdio-tauri'
import type { TaskRequest } from '@/types/protocol'

type TaskEventName =
  | 'task-progress'
  | 'task-log'
  | 'task-completed'
  | 'task-error'
  | 'task-cancelled'

interface CapturedTaskEvent {
  name: TaskEventName
  data: Record<string, unknown>
}

export function buildSoftwareTaskRequest(
  inputPath: string,
  outputDir: string,
  resumeMode: 'auto' | 'force-fresh' | 'force-resume' = 'force-fresh',
): TaskRequest {
  return {
    inputPath,
    outputConfig: { outputDir, openOnComplete: false, segmentFrames: 1000 },
    decodeConfig: {
      mode: 'software',
      hwaccel: null,
      hwaccelDevice: null,
      decoder: 'software',
      options: {},
    },
    encodeConfig: {
      codec: 'h264',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf' as const, value: 23 },
      options: { preset: 'medium' },
    },
    workflowConfig: {
      fpsMode: 'multi' as const,
      processOrder: 'super_resolution_then_interpolation' as const,
      interpolation: {
        enabled: false,
        targetFps: 60,
        multi: 2,
        algorithm: 'rife',
        model: '4.25',
        onnxModel: null,
        scale: 1,
        fp16: false,
        tensorBackend: 'pytorch',
        engine: 'cuda',
      },
      superResolution: {
        enabled: false,
        scaleFactor: 2,
        algorithm: 'realesrgan',
        onnxModel: null,
        tensorBackend: 'pytorch',
        engine: 'cuda',
        numFrames: 10,
      },
      preprocess: { enabled: false, filters: [] },
      postprocess: { enabled: false, filters: [] },
    },
    resumeMode,
  }
}

export async function listenForTaskEvents(
  tauriPage: TauriPage,
  names: TaskEventName[],
): Promise<void> {
  await tauriPage.evaluate(async (eventNames) => {
    const target = window as typeof window & {
      __TAURI_INTERNALS__?: {
        invoke: (command: string, args?: unknown) => Promise<any>
        transformCallback: (callback: (event: any) => void) => number
      }
      __E2E_EVENTS?: CapturedTaskEvent[]
      __E2E_UNLISTENERS?: Array<() => Promise<void>>
    }
    const internals = target.__TAURI_INTERNALS__
    if (!internals) {
      throw new Error('Tauri internals are unavailable')
    }
    target.__E2E_EVENTS = []
    target.__E2E_UNLISTENERS = []

    for (const name of eventNames) {
      const handler = internals.transformCallback((event) => {
        target.__E2E_EVENTS?.push({ name, data: event.payload })
      })
      const eventId = await internals.invoke('plugin:event|listen', {
        event: name,
        target: { kind: 'Any' },
        handler,
      })
      target.__E2E_UNLISTENERS.push(async () => {
        await internals.invoke('plugin:event|unlisten', { event: name, eventId })
      })
    }
  }, names)
}

export async function invokeTauri<T>(
  tauriPage: TauriPage,
  command: string,
  args?: unknown,
): Promise<T> {
  return await tauriPage.evaluate(async (payload) => {
    const target = window as typeof window & {
      __TAURI_INTERNALS__?: { invoke: (name: string, value?: unknown) => Promise<unknown> }
    }
    if (!target.__TAURI_INTERNALS__) {
      throw new Error('Tauri internals are unavailable')
    }
    try {
      return await target.__TAURI_INTERNALS__.invoke(payload.command, payload.args)
    } catch (error) {
      const details = typeof error === 'object' && error !== null
        ? JSON.stringify(error)
        : String(error)
      throw new Error(`${payload.command} failed: ${details}`)
    }
  }, { command, args }) as T
}

export async function captureTauriError(
  tauriPage: TauriPage,
  command: string,
  args?: unknown,
): Promise<{ code?: string, message?: string } | null> {
  return await tauriPage.evaluate(async (payload) => {
    const target = window as typeof window & {
      __TAURI_INTERNALS__?: { invoke: (name: string, value?: unknown) => Promise<unknown> }
    }
    try {
      await target.__TAURI_INTERNALS__?.invoke(payload.command, payload.args)
      return null
    } catch (error) {
      const value = error as { code?: string, message?: string }
      return {
        code: value.code,
        message: value.message ?? (
          typeof error === 'object' && error !== null ? JSON.stringify(error) : String(error)
        ),
      }
    }
  }, { command, args })
}

export async function waitForTaskEvent(
  tauriPage: TauriPage,
  name: TaskEventName,
  timeout = 60000,
): Promise<void> {
  await tauriPage.waitForFunction((eventName) => {
    const events = (window as typeof window & {
      __E2E_EVENTS?: CapturedTaskEvent[]
    }).__E2E_EVENTS ?? []
    return events.some((event) => event.name === eventName)
  }, name, { timeout })
}

export async function readTaskEvents(tauriPage: TauriPage): Promise<CapturedTaskEvent[]> {
  return await tauriPage.evaluate(() => {
    return (window as typeof window & {
      __E2E_EVENTS?: CapturedTaskEvent[]
    }).__E2E_EVENTS ?? []
  })
}

export async function disposeTaskEventListeners(tauriPage: TauriPage): Promise<void> {
  await tauriPage.evaluate(async () => {
    const target = window as typeof window & {
      __E2E_UNLISTENERS?: Array<() => Promise<void>>
    }
    await Promise.allSettled((target.__E2E_UNLISTENERS ?? []).map((unlisten) => unlisten()))
    target.__E2E_UNLISTENERS = []
  })
}
