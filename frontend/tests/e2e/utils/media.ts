import { withPiniaState } from './wdio-tauri'
import type { TaskRequest } from '@/types/protocol'

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
  taskRequest?: TaskRequest
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
      const request = item.taskRequest
      const workflow = clone(request?.workflowConfig ?? draft.workflowConfig)
      if (!request || item.interpolation !== undefined) {
        workflow.interpolation.enabled = item.interpolation ?? false
      }
      if (!request || item.superResolution !== undefined) {
        workflow.superResolution.enabled = item.superResolution ?? false
      }
      const outputConfig = clone(request?.outputConfig ?? draft.outputConfig)
      outputConfig.outputDir = item.outputDir ?? request?.outputConfig.outputDir ?? 'C:/tmp/output'
      return {
        id: item.id,
        displayName: item.displayName,
        inputPath: request?.inputPath ?? `C:/tmp/${item.displayName}`,
        selected: item.selected ?? false,
        inspecting: false,
        info: {
          width: item.width ?? 1920,
          height: item.height ?? 1080,
          fps: item.fps ?? 30,
          videoCodec: item.codec ?? 'h264',
        },
        decodeConfig: clone(request?.decodeConfig ?? draft.decodeConfig),
        workflowConfig: workflow,
        encodeConfig: clone(request?.encodeConfig ?? draft.encodeConfig),
        outputConfig,
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
  phase?: 'idle' | 'running' | 'paused' | 'cancelling'
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

  return await withPiniaState((_state, _win, payload) => {
    type TaskSeedStore = {
      batch?: Record<string, unknown>
      dispatchBatch?: (event: unknown) => void
    }
    type RunStateSeedStore = {
      setTaskState?: (id: string, taskState: unknown) => void
      setLastOutputPath?: (id: string, path: string) => void
    }
    const root = document.querySelector('#app') as HTMLElement & { __vue_app__?: unknown } | null
    const vueApp = root?.__vue_app__ as {
      config?: {
        globalProperties?: {
          $pinia?: {
            _s?: Map<string, TaskSeedStore | RunStateSeedStore>
          }
        }
      }
    } | undefined
    const stores = vueApp?.config?.globalProperties?.$pinia?._s
    const task = stores?.get('task') as TaskSeedStore | undefined
    const runStateStore = stores?.get('mediaRunState') as RunStateSeedStore | undefined
    if (!task?.batch || !task.dispatchBatch || !runStateStore?.setTaskState) {
      return false
    }

    const runtimeIds = Array.from(
      { length: payload.totalCount },
      (_, index) => `batch-item-${index + 1}`,
    )
    if (runtimeIds.length > 0) {
      runtimeIds[Math.min(payload.completedCount, runtimeIds.length - 1)] = payload.itemId
    }
    runtimeIds.forEach((id, index) => {
      runStateStore.setTaskState?.(id, {
        status: index < payload.completedCount ? 'completed' : 'idle',
        logs: [],
        resumeStatus: null,
      })
    })
    runStateStore.setTaskState(payload.itemId, {
      status: payload.phase === 'idle' ? 'completed' : 'running',
      logs: payload.logs,
      resumeStatus: payload.resumeStatus,
    })
    runStateStore.setLastOutputPath?.(payload.itemId, '')
    task.dispatchBatch({ type: 'queue-cleared' })
    task.dispatchBatch({ type: 'item-finalized' })
    if (runtimeIds.length > 0) {
      task.dispatchBatch({ type: 'started', ids: runtimeIds })
      task.dispatchBatch({ type: 'queue-advanced', currentId: payload.itemId, remaining: [] })
      if (payload.phase === 'idle') {
        task.dispatchBatch({ type: 'item-finalized' })
      }
    }
    if (payload.phase === 'paused') {
      task.dispatchBatch({ type: 'control-requested', kind: 'pause' })
      task.dispatchBatch({ type: 'control-succeeded', kind: 'pause' })
    }
    if (payload.phase === 'cancelling') {
      task.dispatchBatch({ type: 'control-requested', kind: 'cancel' })
      if (payload.controlPending !== 'cancel') {
        task.dispatchBatch({ type: 'control-succeeded', kind: 'cancel' })
      }
    } else if (payload.controlPending) {
      task.dispatchBatch({ type: 'control-requested', kind: payload.controlPending })
    }
    return true
  }, {
    itemId,
    logs: options.logs ?? [],
    completedCount: options.completedCount,
    totalCount: options.totalCount,
    phase: options.phase ?? 'idle',
    controlPending: options.controlPending ?? null,
    resumeStatus: options.resumeStatus ?? null,
  })
}
