import { withPiniaState } from './wdio-tauri'

interface MediaSeed {
  id: string
  displayName: string
  selected?: boolean
  outputDir?: string
  width?: number
  height?: number
  fps?: number
  codec?: string
  interpolation?: boolean
  superResolution?: boolean
}

interface MediaSeedPayload {
  activeId?: string
  items: MediaSeed[]
}

export async function seedMediaItems(
  items: MediaSeed[],
  activeId = items[0]?.id,
): Promise<boolean> {
  return await withPiniaState((state, _win, payload: MediaSeedPayload) => {
    const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
    const media = state.media as {
      mediaItems?: unknown[]
      activeItemId?: string | null
    } | undefined
    const draft = (state.preset as {
      draftPreset?: {
        decodeConfig: unknown
        workflowConfig: {
          interpolation: Record<string, unknown>
          superResolution: Record<string, unknown>
        }
        encodeConfig: unknown
        outputConfig: Record<string, unknown>
      }
    } | undefined)?.draftPreset
    if (!media || !draft) {
      return false
    }

    media.mediaItems = payload.items.map((item) => {
      const workflow = clone(draft.workflowConfig)
      workflow.interpolation.enabled = item.interpolation ?? false
      workflow.superResolution.enabled = item.superResolution ?? false
      return {
        id: item.id,
        displayName: item.displayName,
        inputPath: `C:/tmp/${item.displayName}`,
        selected: item.selected ?? false,
        inspecting: false,
        info: {
          width: item.width ?? 1920,
          height: item.height ?? 1080,
          fps: item.fps ?? 30,
          videoCodec: item.codec ?? 'h264',
        },
        decodeConfig: clone(draft.decodeConfig),
        workflowConfig: workflow,
        encodeConfig: clone(draft.encodeConfig),
        outputConfig: {
          ...clone(draft.outputConfig),
          outputDir: item.outputDir ?? 'C:/tmp/output',
        },
      }
    })
    media.activeItemId = payload.activeId ?? null
    return true
  }, { items, activeId })
}

export async function seedTaskConsoleState(options: {
  itemId?: string
  logs?: string[]
  completedCount: number
  totalCount: number
  isRunning?: boolean
  isPaused?: boolean
  isCancelling?: boolean
  controlPending?: 'pause' | 'resume' | 'cancel' | null
  resumeStatus?: {
    resumed: boolean
    completedChunks: number
    completedOutputFrames: number
    totalOutputFrames: number
  } | null
}): Promise<boolean> {
  const itemId = options.itemId ?? 'task-console-item'
  const mediaReady = await seedMediaItems([{
    id: itemId,
    displayName: 'task-console.mp4',
    selected: true,
  }], itemId)
  if (!mediaReady) {
    return false
  }

  return await withPiniaState((state, _win, payload) => {
    const task = state.task as {
      batch?: Record<string, unknown>
      batchRuntimeIds?: string[]
    } | undefined
    const root = document.querySelector('#app') as HTMLElement & { __vue_app__?: unknown } | null
    const vueApp = root?.__vue_app__ as {
      config?: {
        globalProperties?: {
          $pinia?: {
            _s?: Map<string, {
              setTaskState?: (id: string, taskState: unknown) => void
              setLastOutputPath?: (id: string, path: string) => void
            }>
          }
        }
      }
    } | undefined
    const runStateStore = vueApp?.config?.globalProperties?.$pinia?._s?.get('mediaRunState')
    if (!task?.batch || !runStateStore?.setTaskState) {
      return false
    }

    runStateStore.setTaskState(payload.itemId, {
      status: payload.isRunning ? 'running' : 'completed',
      logs: payload.logs,
      resumeStatus: payload.resumeStatus,
    })
    runStateStore.setLastOutputPath?.(payload.itemId, '')
    Object.assign(task.batch, {
      queue: [],
      currentId: payload.itemId,
      completedCount: payload.completedCount,
      isRunning: payload.isRunning,
      isPaused: payload.isPaused,
      isCancelling: payload.isCancelling,
      controlPending: payload.controlPending,
    })
    task.batchRuntimeIds = Array.from(
      { length: payload.totalCount },
      (_, index) => `batch-item-${index + 1}`,
    )
    return true
  }, {
    itemId,
    logs: options.logs ?? [],
    completedCount: options.completedCount,
    totalCount: options.totalCount,
    isRunning: options.isRunning ?? false,
    isPaused: options.isPaused ?? false,
    isCancelling: options.isCancelling ?? false,
    controlPending: options.controlPending ?? null,
    resumeStatus: options.resumeStatus ?? null,
  })
}
