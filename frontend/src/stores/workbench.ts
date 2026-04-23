import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type { UnlistenFn } from '@tauri-apps/api/event'
import {
  cancelTask,
  checkEnvironment as invokeCheckEnvironment,
  inspectVideo as invokeInspectVideo,
  listenTaskEvents,
  loadWorkbenchPreset as invokeLoadWorkbenchPreset,
  openOutputLocation as invokeOpenOutputLocation,
  pickInputs as invokePickInputs,
  pickOutputDirectory as invokePickOutputDirectory,
  saveWorkbenchPreset as invokeSaveWorkbenchPreset,
  startTask as invokeStartTask,
} from '@/lib/tauri'
import {
  buildTaskRequest,
  cloneDecodeConfig,
  cloneEncodeConfig,
  cloneOutputConfig,
  cloneWorkbenchPreset,
  cloneWorkflowConfig,
  createDefaultDecodeConfig,
  createDefaultEncodeConfig,
  createDefaultWorkbenchPreset,
  getVisibleDecoderProfiles,
  getVisibleEncoderProfiles,
} from '@/lib/task-mapper'
import {
  appendTaskLog,
  applyTaskCancelled,
  applyTaskCompleted,
  applyTaskError,
  applyTaskProgress,
  createIdleTaskState,
} from '@/lib/task-events'
import type {
  AppEnv,
  BatchState,
  CapabilityOptionSpec,
  CapabilityValue,
  CodecProfileSpec,
  DecodeConfig,
  DecoderProfileSpec,
  EditingScope,
  EncodeConfig,
  EncoderProfileSpec,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
  GpuAdapter,
  MediaItem,
  OperationIssue,
  OperationIssueScope,
  OutputConfig,
  TaskCompletedPayload,
  TaskError,
  TaskLogPayload,
  TaskProgressPayload,
  VideoInfoResult,
  WorkbenchPreset,
  WorkflowConfig,
} from '@/types'

const PRESET_SAVE_DEBOUNCE_MS = 300

function createInitialEnv(): AppEnv {
  return {
    lastCheckedAt: null,
    lastProbeAt: null,
    checkSource: null,
    isChecking: false,
    isBootstrapping: false,
    checkResult: null,
    issue: null,
  }
}

function createInitialBatch(): BatchState {
  return {
    queue: [],
    currentId: null,
    completedCount: 0,
    failedCount: 0,
    isRunning: false,
  }
}

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
    return {
      code,
      message: error.message,
      details: null,
    }
  }

  return {
    code,
    message: String(error),
    details: null,
  }
}

function normalizeGpuAdapter(adapter: Record<string, unknown>): GpuAdapter {
  return {
    name: String(adapter.name || ''),
    vendor: (adapter.vendor as GpuAdapter['vendor']) ?? 'other',
    deviceType: (adapter.deviceType ?? adapter.device_type ?? 'other') as GpuAdapter['deviceType'],
    adapterCompatibility: String(adapter.adapterCompatibility ?? adapter.adapter_compatibility ?? ''),
    driverVersion: String(adapter.driverVersion ?? adapter.driver_version ?? ''),
  }
}

function normalizeCheckResult(raw: EnvironmentCheckResult): EnvironmentCheckResult {
  const adapters = Array.isArray(raw.gpu?.adapters)
    ? raw.gpu.adapters.map((adapter) => normalizeGpuAdapter(adapter as unknown as Record<string, unknown>))
    : []

  return {
    ...raw,
    ffmpeg: {
      ...raw.ffmpeg,
      hwaccels: raw.ffmpeg?.hwaccels ?? [],
      encoderProfiles: raw.ffmpeg?.encoderProfiles ?? [],
      decoderProfiles: raw.ffmpeg?.decoderProfiles ?? [],
    },
    gpu: {
      ...raw.gpu,
      devices: raw.gpu?.devices ?? [],
      adapters,
    },
  }
}

function normalizeCheckPayload(raw: EnvironmentCheckPayload): EnvironmentCheckPayload {
  return {
    result: normalizeCheckResult(raw.result),
    source: raw.source === 'cache' ? 'cache' : 'probe',
    checkedAt: raw.checkedAt ?? null,
  }
}

function createMediaId(path: string): string {
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${Date.now()}-${path.toLowerCase()}-${suffix}`
}

function basename(path: string): string {
  return path.split(/[/\\]/).pop() ?? path
}

function inferHwaccelForProfile(profile: DecoderProfileSpec | null): string {
  if (!profile) {
    return ''
  }
  if (profile.family === 'nvidia') {
    return 'cuda'
  }
  if (profile.family === 'intel') {
    return 'qsv'
  }
  return ''
}

function defaultRateControlValue(family: EncodeConfig['family']): EncodeConfig['rateControl'] {
  if (family === 'nvidia') {
    return { mode: 'cq', value: 23 }
  }
  if (family === 'intel') {
    return { mode: 'qp', value: 23 }
  }
  return { mode: 'crf', value: 18 }
}

function seedProfileOptions(
  profile: CodecProfileSpec | null,
  currentOptions: Record<string, CapabilityValue> = {},
): Record<string, CapabilityValue> {
  if (!profile) {
    return {}
  }

  const next: Record<string, CapabilityValue> = {}
  for (const option of profile.options) {
    if (option.name in currentOptions) {
      next[option.name] = currentOptions[option.name] as CapabilityValue
      continue
    }
    if (option.defaultValue != null) {
      next[option.name] = option.defaultValue
      continue
    }
    if (option.choices.length > 0) {
      next[option.name] = option.choices[0]?.value ?? ''
      continue
    }
    next[option.name] = option.type === 'boolean' ? false : ''
  }
  return next
}

function coercePreset(raw: WorkbenchPreset | null, env: EnvironmentCheckResult | null): WorkbenchPreset {
  const defaults = createDefaultWorkbenchPreset(env)
  if (!raw) {
    return defaults
  }

  return {
    decodeConfig: raw.decodeConfig ? cloneDecodeConfig(raw.decodeConfig) : defaults.decodeConfig,
    workflowConfig: raw.workflowConfig ? cloneWorkflowConfig(raw.workflowConfig) : defaults.workflowConfig,
    encodeConfig: raw.encodeConfig ? cloneEncodeConfig(raw.encodeConfig) : defaults.encodeConfig,
    outputConfig: raw.outputConfig ? cloneOutputConfig(raw.outputConfig) : defaults.outputConfig,
  }
}

export const useWorkbenchStore = defineStore('workbench', () => {
  const env = reactive<AppEnv>(createInitialEnv())
  const draftPreset = reactive<WorkbenchPreset>(createDefaultWorkbenchPreset(null))
  const mediaItems = ref<MediaItem[]>([])
  const activeItemId = ref<string | null>(null)
  const batch = reactive<BatchState>(createInitialBatch())
  const batchRuntimeIds = ref<string[]>([])
  const operationIssue = ref<OperationIssue | null>(null)

  let detachListenersHandle: UnlistenFn | null = null
  let presetSaveTimer: ReturnType<typeof setTimeout> | null = null
  let presetPersistenceReady = false

  const selectedIds = computed(() => mediaItems.value.filter((item) => item.selected).map((item) => item.id))
  const selectedItems = computed(() => mediaItems.value.filter((item) => item.selected))
  const activeItem = computed(() => mediaItems.value.find((item) => item.id === activeItemId.value) ?? null)
  const currentTaskItem = computed(() => mediaItems.value.find((item) => item.id === batch.currentId) ?? null)
  const batchItems = computed(() => {
    const sourceIds = batchRuntimeIds.value.length > 0 ? batchRuntimeIds.value : selectedIds.value
    const ids = new Set(sourceIds)
    return mediaItems.value.filter((item) => ids.has(item.id))
  })
  const consoleTaskItem = computed(() => currentTaskItem.value ?? activeItem.value)
  const editingScope = computed<EditingScope>(() => (activeItem.value ? 'selection' : 'preset'))
  const editingSelectionCount = computed(() => (activeItem.value ? selectedIds.value.length || 1 : 0))
  const editor = computed<WorkbenchPreset>(() => ({
    decodeConfig: activeItem.value?.decodeConfig ?? draftPreset.decodeConfig,
    workflowConfig: activeItem.value?.workflowConfig ?? draftPreset.workflowConfig,
    encodeConfig: activeItem.value?.encodeConfig ?? draftPreset.encodeConfig,
    outputConfig: activeItem.value?.outputConfig ?? draftPreset.outputConfig,
  }))
  const editorVideoCodec = computed(() => activeItem.value?.info?.video_codec ?? '')
  const visibleEncoderProfiles = computed(() => getVisibleEncoderProfiles(env.checkResult))
  const visibleDecoderProfiles = computed(() =>
    getVisibleDecoderProfiles(env.checkResult, editorVideoCodec.value),
  )
  const currentEncoderProfile = computed<EncoderProfileSpec | null>(() => {
    return (
      visibleEncoderProfiles.value.find((profile) => profile.name === editor.value.encodeConfig.codec) ??
      visibleEncoderProfiles.value[0] ??
      null
    )
  })
  const currentDecoderProfile = computed<DecoderProfileSpec | null>(() => {
    const selectedName =
      editor.value.decodeConfig.mode === 'software' ? 'software' : editor.value.decodeConfig.decoder
    return (
      visibleDecoderProfiles.value.find((profile) => profile.name === selectedName) ??
      visibleDecoderProfiles.value[0] ??
      null
    )
  })
  const allSelected = computed(
    () => mediaItems.value.length > 0 && mediaItems.value.every((item) => item.selected),
  )
  const canStartBatch = computed(
    () => !batch.isRunning && selectedItems.value.length > 0 && selectedItems.value.every((item) => Boolean(item.inputPath)),
  )
  const batchTotal = computed(() => batchRuntimeIds.value.length || selectedItems.value.length)
  const globalTaskStatus = computed(() => {
    if (batch.isRunning) {
      return currentTaskItem.value?.taskState.status ?? 'running'
    }
    return 'idle'
  })

  function replaceDraftPreset(next: WorkbenchPreset): void {
    draftPreset.decodeConfig = cloneDecodeConfig(next.decodeConfig)
    draftPreset.workflowConfig = cloneWorkflowConfig(next.workflowConfig)
    draftPreset.encodeConfig = cloneEncodeConfig(next.encodeConfig)
    draftPreset.outputConfig = cloneOutputConfig(next.outputConfig)
  }

  function schedulePresetSave(): void {
    if (!presetPersistenceReady) {
      return
    }
    if (presetSaveTimer) {
      clearTimeout(presetSaveTimer)
    }
    presetSaveTimer = setTimeout(() => {
      presetSaveTimer = null
      void persistWorkbenchPreset()
    }, PRESET_SAVE_DEBOUNCE_MS)
  }

  async function persistWorkbenchPreset(): Promise<void> {
    try {
      await invokeSaveWorkbenchPreset(cloneWorkbenchPreset(draftPreset))
    } catch {
      // Ignore persistence failures and keep the in-memory editor usable.
    }
  }

  async function loadPersistedPreset(): Promise<boolean> {
    try {
      const preset = await invokeLoadWorkbenchPreset()
      if (!preset) {
        replaceDraftPreset(createDefaultWorkbenchPreset(env.checkResult))
        return false
      }
      replaceDraftPreset(coercePreset(preset, env.checkResult))
      return true
    } catch {
      replaceDraftPreset(createDefaultWorkbenchPreset(env.checkResult))
      return false
    }
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

  function findItem(id: string | null): MediaItem | null {
    if (!id) {
      return null
    }
    return mediaItems.value.find((item) => item.id === id) ?? null
  }

  function setOperationIssue(scope: OperationIssueScope, error: TaskError): void {
    operationIssue.value = {
      scope,
      error,
    }
  }

  function clearOperationIssue(scope?: OperationIssueScope): void {
    if (!scope || operationIssue.value?.scope === scope) {
      operationIssue.value = null
    }
  }

  function normalizeDraftPresetProfiles(preferDefaults = false): void {
    draftPreset.decodeConfig = normalizeDecodeConfig(draftPreset.decodeConfig, '', preferDefaults)
    draftPreset.encodeConfig = normalizeEncodeConfig(draftPreset.encodeConfig, preferDefaults)
  }

  function normalizeDecodeConfig(
    config: DecodeConfig,
    videoCodec: string,
    preferDefaults = false,
  ): DecodeConfig {
    const visibleProfiles = getVisibleDecoderProfiles(env.checkResult, videoCodec)
    const allProfiles = getVisibleDecoderProfiles(env.checkResult, '')

    if (preferDefaults) {
      return createDefaultDecodeConfig(env.checkResult, videoCodec)
    }

    const selectedName = config.mode === 'software' ? 'software' : config.decoder
    const matchedVisible = visibleProfiles.find((profile) => profile.name === selectedName) ?? null
    if (matchedVisible) {
      if (matchedVisible.family === 'software') {
        return {
          mode: 'software',
          hwaccel: '',
          hwaccelDevice: '',
          decoder: 'software',
          options: {},
        }
      }

      return {
        ...config,
        mode: 'hardware',
        hwaccel: inferHwaccelForProfile(matchedVisible),
        hwaccelDevice: config.hwaccelDevice,
        decoder: matchedVisible.name,
        options: seedProfileOptions(matchedVisible, config.options),
      }
    }

    const currentProfile = allProfiles.find((profile) => profile.name === selectedName) ?? null
    const remappedProfile = currentProfile
      ? visibleProfiles.find((profile) => profile.family === currentProfile.family) ?? null
      : null
    if (remappedProfile && remappedProfile.family !== 'software') {
      return {
        ...config,
        mode: 'hardware',
        hwaccel: inferHwaccelForProfile(remappedProfile),
        hwaccelDevice: config.hwaccelDevice,
        decoder: remappedProfile.name,
        options: seedProfileOptions(remappedProfile, config.options),
      }
    }

    return createDefaultDecodeConfig(env.checkResult, videoCodec)
  }

  function normalizeEncodeConfig(config: EncodeConfig, preferDefaults = false): EncodeConfig {
    const profiles = getVisibleEncoderProfiles(env.checkResult)
    const matchedProfile = profiles.find((profile) => profile.name === config.codec) ?? null

    if (preferDefaults || !matchedProfile) {
      const fallbackProfile = profiles.find((profile) => profile.family === config.family) ?? null
      const defaults = createDefaultEncodeConfig(env.checkResult)
      const candidate = preferDefaults ? null : fallbackProfile
      if (!candidate) {
        return {
          ...defaults,
          container: config.container || defaults.container,
          keepAudio: config.keepAudio,
        }
      }

      const family =
        candidate.family === 'nvidia' || candidate.family === 'intel' ? candidate.family : 'cpu'
      return {
        ...config,
        codec: candidate.name,
        family,
        rateControl: defaultRateControlValue(family),
        options: seedProfileOptions(candidate, config.options),
      }
    }

    return {
      ...config,
      family:
        matchedProfile.family === 'nvidia' || matchedProfile.family === 'intel'
          ? matchedProfile.family
          : 'cpu',
      options: seedProfileOptions(matchedProfile, config.options),
    }
  }

  function normalizeItemProfiles(item: MediaItem, preferDefaults = false): void {
    item.decodeConfig = normalizeDecodeConfig(item.decodeConfig, item.info?.video_codec ?? '', preferDefaults)
    item.encodeConfig = normalizeEncodeConfig(item.encodeConfig, preferDefaults)
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
    if (batch.isRunning) {
      return
    }

    const index = mediaItems.value.findIndex((item) => item.id === id)
    if (index < 0) {
      return
    }

    mediaItems.value.splice(index, 1)
    if (activeItemId.value === id) {
      activeItemId.value = mediaItems.value[0]?.id ?? null
    }
  }

  function patchWorkflow(mutator: (config: WorkflowConfig) => void): void {
    const nextDraft = cloneWorkflowConfig(draftPreset.workflowConfig)
    mutator(nextDraft)
    draftPreset.workflowConfig = nextDraft

    forEachEditableItem((item) => {
      const next = cloneWorkflowConfig(item.workflowConfig)
      mutator(next)
      item.workflowConfig = next
    })

    schedulePresetSave()
  }

  function patchDecode(mutator: (config: DecodeConfig) => void): void {
    const nextDraft = cloneDecodeConfig(draftPreset.decodeConfig)
    mutator(nextDraft)
    draftPreset.decodeConfig = nextDraft
    normalizeDraftPresetProfiles()

    forEachEditableItem((item) => {
      const next = cloneDecodeConfig(item.decodeConfig)
      mutator(next)
      item.decodeConfig = next
    })

    schedulePresetSave()
  }

  function patchEncode(mutator: (config: EncodeConfig) => void): void {
    const nextDraft = cloneEncodeConfig(draftPreset.encodeConfig)
    mutator(nextDraft)
    draftPreset.encodeConfig = nextDraft
    normalizeDraftPresetProfiles()

    forEachEditableItem((item) => {
      const next = cloneEncodeConfig(item.encodeConfig)
      mutator(next)
      item.encodeConfig = next
    })

    schedulePresetSave()
  }

  function patchOutput(mutator: (config: OutputConfig) => void): void {
    const nextDraft = cloneOutputConfig(draftPreset.outputConfig)
    mutator(nextDraft)
    draftPreset.outputConfig = nextDraft

    forEachEditableItem((item) => {
      const next = cloneOutputConfig(item.outputConfig)
      mutator(next)
      item.outputConfig = next
    })

    schedulePresetSave()
  }

  function setDecodeProfile(profileName: string): void {
    const profile = visibleDecoderProfiles.value.find((entry) => entry.name === profileName) ?? null
    patchDecode((config) => {
      if (!profile || profile.family === 'software') {
        config.mode = 'software'
        config.hwaccel = ''
        config.hwaccelDevice = ''
        config.decoder = 'software'
        config.options = {}
        return
      }

      config.mode = 'hardware'
      config.hwaccel = inferHwaccelForProfile(profile)
      config.decoder = profile.name
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setDecodeHwaccelDevice(value: string): void {
    patchDecode((config) => {
      config.hwaccelDevice = value
    })
  }

  function setDecodeOption(optionName: string, value: CapabilityValue): void {
    patchDecode((config) => {
      config.options = {
        ...config.options,
        [optionName]: value,
      }
    })
  }

  function setEncodeProfile(profileName: string): void {
    const profile = visibleEncoderProfiles.value.find((entry) => entry.name === profileName) ?? null
    if (!profile) {
      return
    }

    patchEncode((config) => {
      config.codec = profile.name
      config.family =
        profile.family === 'nvidia' || profile.family === 'intel' ? profile.family : 'cpu'
      config.rateControl = defaultRateControlValue(
        profile.family === 'nvidia' || profile.family === 'intel' ? profile.family : 'cpu',
      )
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setEncodeRateControlMode(mode: EncodeConfig['rateControl']['mode']): void {
    patchEncode((config) => {
      config.rateControl = {
        mode,
        value: config.rateControl.value,
      }
    })
  }

  function setEncodeRateControlValue(value: number): void {
    patchEncode((config) => {
      config.rateControl = {
        ...config.rateControl,
        value,
      }
    })
  }

  function setEncodeOption(optionName: string, value: CapabilityValue): void {
    patchEncode((config) => {
      config.options = {
        ...config.options,
        [optionName]: value,
      }
    })
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
      decodeConfig: cloneDecodeConfig(draftPreset.decodeConfig),
      workflowConfig: cloneWorkflowConfig(draftPreset.workflowConfig),
      encodeConfig: cloneEncodeConfig(draftPreset.encodeConfig),
      outputConfig: cloneOutputConfig(draftPreset.outputConfig),
      taskState: createIdleTaskState(),
      lastOutputPath: '',
    }

    normalizeItemProfiles(item)
    return item
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
    clearOperationIssue('input')
    await inspectItems(freshItems.map((item) => item.id))
  }

  async function pickInputs(): Promise<void> {
    try {
      const paths = await invokePickInputs()
      clearOperationIssue('input')
      await addMediaPaths(paths)
    } catch (error) {
      setOperationIssue('input', normalizeTaskError(error, 'pick_inputs_failed'))
    }
  }

  async function recheckEnvironment(forceRefresh = true): Promise<void> {
    env.isChecking = true
    env.issue = null
    try {
      const payload = normalizeCheckPayload((await invokeCheckEnvironment(forceRefresh)) as EnvironmentCheckPayload)
      env.checkResult = payload.result
      env.checkSource = payload.source
      env.lastCheckedAt = new Date().toISOString()
      env.lastProbeAt = payload.checkedAt ?? env.lastCheckedAt
      normalizeDraftPresetProfiles()
      for (const item of mediaItems.value) {
        normalizeItemProfiles(item)
      }
      schedulePresetSave()
    } catch (error) {
      env.issue = normalizeTaskError(error, 'check_failed')
    } finally {
      env.isChecking = false
    }
  }

  async function bootstrap(): Promise<void> {
    if (env.isBootstrapping) {
      return
    }

    env.isBootstrapping = true
    try {
      await attachTaskListeners()
      const hasPersistedPreset = await loadPersistedPreset()
      await recheckEnvironment(false)
      if (!hasPersistedPreset && env.checkResult) {
        replaceDraftPreset(createDefaultWorkbenchPreset(env.checkResult))
      }
      presetPersistenceReady = true
      schedulePresetSave()
    } finally {
      env.isBootstrapping = false
    }
  }

  async function attachTaskListeners(): Promise<void> {
    if (detachListenersHandle) {
      return
    }

    detachListenersHandle = await listenTaskEvents({
      onProgress(payload) {
        applyEventToCurrentItem((item) => {
          item.taskState = applyTaskProgress(item.taskState, payload as TaskProgressPayload)
        })
      },
      onLog(payload) {
        applyEventToCurrentItem((item) => {
          item.taskState = appendTaskLog(item.taskState, payload as TaskLogPayload)
        })
      },
      onCompleted(payload) {
        void handleCurrentTaskCompleted(payload as TaskCompletedPayload)
      },
      onError(error) {
        void handleCurrentTaskErrored(error)
      },
      onCancelled() {
        void handleCurrentTaskCancelled()
      },
    })
  }

  function detachTaskListeners(): void {
    if (presetSaveTimer) {
      clearTimeout(presetSaveTimer)
      presetSaveTimer = null
    }
    detachListenersHandle?.()
    detachListenersHandle = null
  }

  function applyEventToCurrentItem(mutator: (item: MediaItem) => void): void {
    const item = currentTaskItem.value ?? activeItem.value
    if (!item) {
      return
    }
    mutator(item)
  }

  function resetItemRunState(item: MediaItem): void {
    item.taskState = createIdleTaskState()
    item.issue = null
    item.lastOutputPath = ''
  }

  function clearBatchRuntimeArtifacts(): void {
    const runtimeIds = new Set(batchRuntimeIds.value)
    for (const item of mediaItems.value) {
      if (!runtimeIds.has(item.id)) {
        continue
      }
      resetItemRunState(item)
    }
  }

  function resetBatchCounters(): void {
    batch.completedCount = 0
    batch.failedCount = 0
  }

  function resetBatchRunState(ids: string[]): void {
    batchRuntimeIds.value = [...ids]
    batch.queue = [...ids]
    batch.currentId = null
    resetBatchCounters()
    batch.isRunning = ids.length > 0

    const queuedIds = new Set(ids)
    for (const item of mediaItems.value) {
      if (!queuedIds.has(item.id)) {
        continue
      }
      resetItemRunState(item)
    }
  }

  async function runNextQueuedItem(): Promise<void> {
    const nextId = batch.queue.shift() ?? null
    if (!nextId) {
      batch.currentId = null
      batch.isRunning = false
      return
    }

    const item = findItem(nextId)
    if (!item) {
      batch.currentId = null
      await runNextQueuedItem()
      return
    }

    batch.currentId = nextId
    activeItemId.value = nextId
    item.taskState = {
      ...createIdleTaskState(),
      status: 'running',
      startedAt: new Date().toISOString(),
    }

    try {
      await invokeStartTask(buildTaskRequest(item))
    } catch (error) {
      await handleCurrentTaskErrored(normalizeTaskError(error, 'start_failed'))
    }
  }

  async function finalizeCurrentTask(state: 'completed' | 'error' | 'cancelled'): Promise<void> {
    const item = currentTaskItem.value
    if (!item) {
      batch.currentId = null
      if (batch.queue.length > 0) {
        await runNextQueuedItem()
      } else {
        batch.isRunning = false
        clearBatchRuntimeArtifacts()
        resetBatchCounters()
        batchRuntimeIds.value = []
      }
      return
    }

    if (state === 'completed') {
      if (item.outputConfig.openOnComplete && item.lastOutputPath) {
        try {
          await invokeOpenOutputLocation(item.lastOutputPath)
        } catch {
          // Ignore shell-open failures after processing finished.
        }
      }
      batch.completedCount += 1
    } else {
      batch.failedCount += 1
    }

    batch.currentId = null
    if (batch.queue.length > 0) {
      await runNextQueuedItem()
      return
    }

    batch.isRunning = false
    clearBatchRuntimeArtifacts()
    resetBatchCounters()
    batchRuntimeIds.value = []
  }

  async function handleCurrentTaskCompleted(payload: TaskCompletedPayload): Promise<void> {
    const item = currentTaskItem.value
    if (item) {
      item.taskState = applyTaskCompleted(item.taskState, payload)
      item.lastOutputPath = payload.outputPath ?? item.lastOutputPath
    }
    await finalizeCurrentTask('completed')
  }

  async function handleCurrentTaskErrored(error: TaskError): Promise<void> {
    const item = currentTaskItem.value
    if (item) {
      item.taskState = applyTaskError(item.taskState, error)
      item.issue = error
    }
    await finalizeCurrentTask('error')
  }

  async function handleCurrentTaskCancelled(): Promise<void> {
    const item = currentTaskItem.value
    if (item) {
      item.taskState = applyTaskCancelled(item.taskState)
    }
    await finalizeCurrentTask('cancelled')
  }

  async function startBatch(): Promise<void> {
    if (!canStartBatch.value) {
      return
    }
    clearOperationIssue('task')
    clearOperationIssue('output')
    resetBatchRunState(selectedIds.value)
    await runNextQueuedItem()
  }

  async function cancelCurrentTask(): Promise<void> {
    if (!batch.isRunning) {
      return
    }
    try {
      await cancelTask()
      clearOperationIssue('task')
    } catch (error) {
      setOperationIssue('task', normalizeTaskError(error, 'cancel_failed'))
    }
  }

  async function pickOutputDirectory(): Promise<void> {
    try {
      const outputDir = await invokePickOutputDirectory()
      clearOperationIssue('encode')
      if (!outputDir) {
        return
      }
      patchOutput((config) => {
        config.outputDir = outputDir
      })
    } catch (error) {
      setOperationIssue('encode', normalizeTaskError(error, 'pick_output_dir_failed'))
    }
  }

  async function openOutputLocation(path?: string): Promise<void> {
    const target =
      path ||
      currentTaskItem.value?.lastOutputPath ||
      currentTaskItem.value?.taskState.outputPath ||
      activeItem.value?.outputConfig.outputDir ||
      draftPreset.outputConfig.outputDir ||
      ''
    if (!target) {
      return
    }
    try {
      await invokeOpenOutputLocation(target)
      clearOperationIssue('output')
    } catch (error) {
      setOperationIssue('output', normalizeTaskError(error, 'open_output_failed'))
    }
  }

  function getOptionValue(
    option: CapabilityOptionSpec,
    values: Record<string, CapabilityValue>,
  ): CapabilityValue {
    if (option.name in values) {
      return values[option.name] as CapabilityValue
    }
    if (option.defaultValue != null) {
      return option.defaultValue
    }
    if (option.type === 'boolean') {
      return false
    }
    if (option.choices.length > 0) {
      return option.choices[0]?.value ?? ''
    }
    return ''
  }

  return {
    env,
    draftPreset,
    mediaItems,
    activeItemId,
    batch,
    operationIssue,
    selectedIds,
    selectedItems,
    activeItem,
    currentTaskItem,
    batchItems,
    consoleTaskItem,
    editor,
    editingScope,
    editingSelectionCount,
    visibleEncoderProfiles,
    visibleDecoderProfiles,
    currentEncoderProfile,
    currentDecoderProfile,
    allSelected,
    canStartBatch,
    batchTotal,
    globalTaskStatus,
    bootstrap,
    recheckEnvironment,
    clearOperationIssue,
    attachTaskListeners,
    detachTaskListeners,
    addMediaPaths,
    pickInputs,
    inspectItems,
    inspectMediaItem,
    setActiveItem,
    selectAllMedia,
    setItemSelected,
    removeMediaItem,
    patchWorkflow,
    patchDecode,
    patchEncode,
    patchOutput,
    setDecodeProfile,
    setDecodeHwaccelDevice,
    setDecodeOption,
    setEncodeProfile,
    setEncodeRateControlMode,
    setEncodeRateControlValue,
    setEncodeOption,
    startBatch,
    cancelCurrentTask,
    pickOutputDirectory,
    openOutputLocation,
    getOptionValue,
  }
})
