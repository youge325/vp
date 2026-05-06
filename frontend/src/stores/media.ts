import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { inspectVideo as invokeInspectVideo, pickInputs as invokePickInputs } from '@/lib/tauri'
import { cloneDecodeConfig, cloneEncodeConfig, cloneOutputConfig, cloneWorkflowConfig, normalizeTaskError } from '@/lib/task-mapper'
import type { MediaItem, VideoInfoResult } from '@/types'

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
    resumeStatus: null,
  }
}

export const useMediaStore = defineStore('media', () => {
  const mediaItems = ref<MediaItem[]>([])
  const activeItemId = ref<string | null>(null)

  const selectedIds = computed(() => mediaItems.value.filter((item) => item.selected).map((item) => item.id))
  const selectedItems = computed(() => mediaItems.value.filter((item) => item.selected))
  const activeItem = computed(() => mediaItems.value.find((item) => item.id === activeItemId.value) ?? null)
  const allSelected = computed(
    () => mediaItems.value.length > 0 && mediaItems.value.every((item) => item.selected),
  )

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

  function createMediaItem(path: string, preset: import('@/types').WorkbenchPreset): MediaItem {
    const item: MediaItem = {
      id: createMediaId(path),
      inputPath: path,
      displayName: basename(path),
      selected: true,
      inspecting: false,
      info: null,
      issue: null,
      decodeConfig: cloneDecodeConfig(preset.decodeConfig),
      workflowConfig: cloneWorkflowConfig(preset.workflowConfig),
      encodeConfig: cloneEncodeConfig(preset.encodeConfig),
      outputConfig: cloneOutputConfig(preset.outputConfig),
      taskState: createIdleTaskState(),
      lastOutputPath: '',
    }

    // normalizeItemProfiles 在 inspect 之后通过外部传入的函数调用
    return item
  }

  function normalizeItemProfiles(
    item: MediaItem,
    normalizeDecodeFn: (config: MediaItem['decodeConfig'], codec: string, preferDefaults?: boolean) => MediaItem['decodeConfig'],
    normalizeEncodeFn: (config: MediaItem['encodeConfig'], preferDefaults?: boolean) => MediaItem['encodeConfig'],
    preferDefaults = false,
  ): void {
    item.decodeConfig = normalizeDecodeFn(item.decodeConfig, item.info?.videoCodec ?? '', preferDefaults)
    item.encodeConfig = normalizeEncodeFn(item.encodeConfig, preferDefaults)
  }

  async function inspectMediaItem(
    id: string,
    normalizeDecodeFn?: (config: MediaItem['decodeConfig'], codec: string, preferDefaults?: boolean) => MediaItem['decodeConfig'],
    normalizeEncodeFn?: (config: MediaItem['encodeConfig'], preferDefaults?: boolean) => MediaItem['encodeConfig'],
  ): Promise<void> {
    const item = findItem(id)
    if (!item || item.inspecting) {
      return
    }

    item.inspecting = true
    item.issue = null
    try {
      const info = (await invokeInspectVideo(item.inputPath)) as VideoInfoResult
      item.info = info
      if (normalizeDecodeFn && normalizeEncodeFn) {
        normalizeItemProfiles(item, normalizeDecodeFn, normalizeEncodeFn)
      }
    } catch (error) {
      item.issue = normalizeTaskError(error, 'inspect_failed')
    } finally {
      item.inspecting = false
    }
  }

  async function inspectItems(
    ids: string[],
    normalizeDecodeFn?: (config: MediaItem['decodeConfig'], codec: string, preferDefaults?: boolean) => MediaItem['decodeConfig'],
    normalizeEncodeFn?: (config: MediaItem['encodeConfig'], preferDefaults?: boolean) => MediaItem['encodeConfig'],
  ): Promise<void> {
    await Promise.allSettled(ids.map((id) => inspectMediaItem(id, normalizeDecodeFn, normalizeEncodeFn)))
  }

  async function addMediaPaths(
    paths: string[],
    preset: import('@/types').WorkbenchPreset,
    normalizeDecodeFn?: (config: MediaItem['decodeConfig'], codec: string, preferDefaults?: boolean) => MediaItem['decodeConfig'],
    normalizeEncodeFn?: (config: MediaItem['encodeConfig'], preferDefaults?: boolean) => MediaItem['encodeConfig'],
  ): Promise<void> {
    const normalizedPaths = paths.filter(Boolean)
    const existing = new Set(mediaItems.value.map((item) => item.inputPath.toLowerCase()))
    const freshItems = normalizedPaths
      .filter((path) => !existing.has(path.toLowerCase()))
      .map((path) => createMediaItem(path, preset))

    if (freshItems.length === 0) {
      return
    }

    mediaItems.value.push(...freshItems)
    activeItemId.value = freshItems[0]?.id ?? activeItemId.value
    await inspectItems(freshItems.map((item) => item.id), normalizeDecodeFn, normalizeEncodeFn)
  }

  async function pickInputs(): Promise<{ paths: string[]; error: import('@/types').TaskError | null }> {
    try {
      const paths = await invokePickInputs()
      return { paths, error: null }
    } catch (error) {
      return { paths: [], error: normalizeTaskError(error, 'pick_inputs_failed') }
    }
  }

  function setActiveItem(id: string | null): void {
    if (id === null) {
      activeItemId.value = null
      return
    }
    if (findItem(id)) {
      activeItemId.value = id
    }
  }

  function resetItemRunState(
    item: { taskState: ReturnType<typeof createIdleTaskState>; issue: import('@/types').TaskError | null; lastOutputPath: string },
    preserveLogs: boolean = false,
  ): void {
    const existingLogs = preserveLogs ? item.taskState.logs : []
    item.taskState = { ...createIdleTaskState(), logs: existingLogs }
    item.issue = null
    item.lastOutputPath = ''
  }

  function resetItemsRunState(ids: Set<string>, preserveLogs: boolean = false): void {
    for (const item of mediaItems.value) {
      if (ids.has(item.id)) {
        resetItemRunState(item, preserveLogs)
      }
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
    resetItemRunState,
    resetItemsRunState,
    selectAllMedia,
    setItemSelected,
    removeMediaItem,
  }
})
