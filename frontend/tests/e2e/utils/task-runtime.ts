import type { TauriPage } from './wdio-tauri'
import type {
  IpcCommand,
  IpcInvokeArgs,
  IpcInvokeResult,
} from '@/lib/ipc/contract'
import type {
  ResumeMode,
  TaskEventName,
  TaskEventPayloadMap,
  TaskRequest,
} from '@/types/protocol'
import { TASK_EVENT_NAMES } from '../../../src/types/protocol/events'

type CapturedTaskEvent<Name extends TaskEventName = TaskEventName> =
  Name extends TaskEventName
    ? { name: Name, data: TaskEventPayloadMap[Name] }
    : never

export function buildSoftwareTaskRequest(
  inputPath: string,
  outputDir: string,
  resumeMode: ResumeMode = 'force-fresh',
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
  names: readonly TaskEventName[] = Object.values(TASK_EVENT_NAMES),
): Promise<void> {
  await tauriPage.evaluate(async (eventNames) => {
    const target = window as typeof window & {
      __TAURI_INTERNALS__?: {
        invoke: (command: string, args?: unknown) => Promise<unknown>
        transformCallback: (callback: (event: { payload: unknown }) => void) => number
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
        target.__E2E_EVENTS?.push({
          name,
          data: event.payload,
        } as CapturedTaskEvent)
      })
      const eventId = await internals.invoke('plugin:event|listen', {
        event: name,
        target: { kind: 'Any' },
        handler,
      }) as number
      target.__E2E_UNLISTENERS.push(async () => {
        await internals.invoke('plugin:event|unlisten', { event: name, eventId })
      })
    }
  }, names)
}

export async function invokeTauri<C extends IpcCommand>(
  tauriPage: TauriPage,
  command: C,
  ...args: IpcInvokeArgs<C> extends undefined ? [] : [args: IpcInvokeArgs<C>]
): Promise<IpcInvokeResult<C>> {
  const commandArgs = args[0]
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
  }, { command, args: commandArgs }) as IpcInvokeResult<C>
}

export async function captureTauriError<C extends IpcCommand>(
  tauriPage: TauriPage,
  command: C,
  ...args: IpcInvokeArgs<C> extends undefined ? [] : [args: IpcInvokeArgs<C>]
): Promise<{ code?: string, message?: string } | null> {
  const commandArgs = args[0]
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
  }, { command, args: commandArgs })
}

export function isTaskEvent<Name extends TaskEventName>(name: Name) {
  return (event: CapturedTaskEvent): event is CapturedTaskEvent<Name> => event.name === name
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
