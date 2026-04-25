import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { inspectVideo as invokeInspectVideo } from '@/lib/tauri'
import { cloneDecodeConfig, cloneEncodeConfig, cloneOutputConfig, cloneWorkflowConfig } from '@/lib/task-mapper'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { MediaItem, TaskError, VideoInfoResult } from '@/types'

function normalizeTaskError(error: unknown, code = 'runtime_error'): TaskError {
  if (typeof error === 'object' && error !== null && 'code' in error && 'message' in error) {
    const payload = error as { code?: unknown; message?: unknown; details?: Record<string, unknown> | null }
    return {
      code: typeof payload.code === 'string' ? payload.code : code,
      message: typeof payload.message === 'string' ? payload.message : 'Execution failed.',
      details: payload.details ?? null,
    }
  }

  if (error instanceof Error) {
    return { code, message: error.message, details: null }
  }

  return { code, message: String(error), details: null }
}

function createMediaId(path: string): string {
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${Date.now()}-${path.toLowerCase()}-${suffix}`
}

function basename(path: string): string {
  return path.split(/[/\\]/).pop() ?? path
}

function createIdleTaskState(): import('@/types').MediaTaskState {
  return {
    status: 'idle',
    percent: 0,
    current: 0,
    total: 0,
    stage: '',
    stageIndex: 0,
    stageTotal: 0,
    logs: [],
    outputPath: '',
    processedFrames: 0,
    timeSeconds: 0,
    error: null,
    startedAt: null,
    finishedAt: null,
  }
}

export const useMediaStore = defineStore('media', () => {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()

  const mediaItems = ref<MediaItem[]>([])
  const activeItemId = ref<string | null>(null)

  const selectedIds = computed(() => mediaItems.value.filter((item) => item.selected).map((item) => item.id))
  const selectedItems = computed(() => mediaItems.value.filter((item) => item.selected))
  const activeItem = computed(() => mediaItems.value.find((item) => item.id === activeItemId.value) ?? null)
  const allSelected = computed(
    () => mediaItems.value.length > 0 && mediaItems.value.every((item) => item.selected),
  )
  const editingScope = computed(() => (activeItem.value ? 'selection' : 'preset'))
  const editingSelectionCount = computed(() => (activeItem.value ? selectedIds.value.length || 1 : 0))

  const editor = computed(() => ({
    decodeConfig: activeItem.value?.decodeConfig ?? presetStore.draftPreset.decodeConfig,
    workflowConfig: activeItem.value?.workflowConfig ?? presetStore.draftPreset.workflowConfig,
    encodeConfig: activeItem.value?.encodeConfig ?? presetStore.draftPreset.encodeConfig,
    outputConfig: activeItem.value?.outputConfig ?? presetStore.draftPreset.outputConfig,
  }))

  const editorVideoCodec = computed(() => activeItem.value?.info?.video_codec ?? '')

  function findItem(id: string | null): MediaItem | null {
    if (!id) {
      return null
    }
    return mediaItems.value.find((item) => item.id === id) ?? null
  }

  function getEditableTargetIds(): Set<string> {
    const targetIds = new Set<string>(selectedIds.value)
    if (activeItemId.value) {
      targetIds.add(activeItemId.value)
    }
    return targetIds
  }

  function forEachEditableItem(callback: (item: MediaItem) => void): void {
    const targetIds = getEditableTargetIds()
    for (const item of mediaItems.value) {
      if (targetIds.has(item.id)) {
        callback(item)
      }
    }
  }

  function createMediaItem(path: string): MediaItem {
    const item: MediaItem = {
      id: createMediaId(path),
      inputPath: path,
      displayName: basename(path),
      selected: true,
      inspecting: false,
      info: null,
      issue: null,
      decodeConfig: cloneDecodeConfig(presetStore.draftPreset.decodeConfig),
      workflowConfig: cloneWorkflowConfig(presetStore.draftPreset.workflowConfig),
      encodeConfig: cloneEncodeConfig(presetStore.draftPreset.encodeConfig),
      outputConfig: cloneOutputConfig(presetStore.draftPreset.outputConfig),
      taskState: createIdleTaskState(),
      lastOutputPath: '',
    }

    normalizeItemProfiles(item)
    return item
  }

  function normalizeItemProfiles(item: MediaItem, preferDefaults = false): void {
    item.decodeConfig = presetStore.normalizeDecodeConfig(item.decodeConfig, item.info?.video_codec ?? '', preferDefaults)
    item.encodeConfig = presetStore.normalizeEncodeConfig(item.encodeConfig, preferDefaults)
  }

  async function inspectMediaItem(id: string): Promise<void> {
    const item = findItem(id)
    if (!item || item.inspecting) {
      return
    }

    item.inspecting = true
    item.issue = null
    try {
      const info = (await invokeInspectVideo(item.inputPath)) as VideoInfoResult
      item.info = info
      normalizeItemProfiles(item)
    } catch (error) {
      item.issue = normalizeTaskError(error, 'inspect_failed')
    } finally {
      item.inspecting = false
    }
  }

  async function inspectItems(ids: string[]): Promise<void> {
    await Promise.allSettled(ids.map((id) => inspectMediaItem(id)))
  }

  async function addMediaPaths(paths: string[]): Promise<void> {
    const normalizedPaths = paths.filter(Boolean)
    const existing = new Set(mediaItems.value.map((item) => item.inputPath.toLowerCase()))
    const freshItems = normalizedPaths
      .filter((path) => !existing.has(path.toLowerCase()))
      .map((path) => createMediaItem(path))

    if (freshItems.length === 0) {
      return
    }

    mediaItems.value.push(...freshItems)
    activeItemId.value = freshItems[0]?.id ?? activeItemId.value
    envStore.clearOperationIssue('input')
    await inspectItems(freshItems.map((item) => item.id))
  }

  async function pickInputs(): Promise<void> {
    try {
      const { pickInputs: tauriPickInputs } = await import('@/lib/tauri')
      const paths = await tauriPickInputs()
      envStore.clearOperationIssue('input')
      await addMediaPaths(paths)
    } catch (error) {
      envStore.setOperationIssue('input', normalizeTaskError(error, 'pick_inputs_failed'))
    }
  }

  function setActiveItem(id: string): void {
    if (findItem(id)) {
      activeItemId.value = id
    }
  }

  function selectAllMedia(selected: boolean): void {
    for (const item of mediaItems.value) {
      item.selected = selected
    }
  }

  function setItemSelected(id: string, selected: boolean): void {
    const item = findItem(id)
    if (!item) {
      return
    }
    item.selected = selected
  }

  function removeMediaItem(id: string): void {
    const index = mediaItems.value.findIndex((item) => item.id === id)
    if (index < 0) {
      return
    }

    mediaItems.value.splice(index, 1)
    if (activeItemId.value === id) {
      activeItemId.value = mediaItems.value[0]?.id ?? null
    }
  }

  return {
    mediaItems,
    activeItemId,
    selectedIds,
    selectedItems,
    activeItem,
    allSelected,
    editingScope,
    editingSelectionCount,
    editor,
    editorVideoCodec,
    findItem,
    getEditableTargetIds,
    forEachEditableItem,
    createMediaItem,
    normalizeItemProfiles,
    inspectMediaItem,
    inspectItems,
    addMediaPaths,
    pickInputs,
    setActiveItem,
    selectAllMedia,
    setItemSelected,
    removeMediaItem,
  }
})
