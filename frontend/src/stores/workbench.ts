import { computed } from 'vue'
import { defineStore } from 'pinia'
import {
  cloneDecodeConfig,
  cloneEncodeConfig,
  cloneOutputConfig,
  cloneWorkflowConfig,
  getVisibleDecoderProfiles,
} from '@/lib/task-mapper'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'

export const useWorkbenchStore = defineStore('workbench', () => {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()
  const mediaStore = useMediaStore()
  const taskStore = useTaskStore()

  // Delegated state / computed
  const env = computed(() => envStore.env)
  const draftPreset = computed(() => presetStore.draftPreset)
  const mediaItems = computed(() => mediaStore.mediaItems)
  const activeItemId = computed(() => mediaStore.activeItemId)
  const batch = computed(() => taskStore.batch)
  const operationIssue = computed(() => envStore.operationIssue)

  const selectedIds = computed(() => mediaStore.selectedIds)
  const selectedItems = computed(() => mediaStore.selectedItems)
  const activeItem = computed(() => mediaStore.activeItem)
  const currentTaskItem = computed(() => taskStore.currentTaskItem)
  const batchItems = computed(() => {
    const sourceIds = taskStore.batchRuntimeIds.length > 0 ? taskStore.batchRuntimeIds : mediaStore.selectedIds
    const ids = new Set(sourceIds)
    return mediaStore.mediaItems.filter((item) => ids.has(item.id))
  })
  const consoleTaskItem = computed(() => taskStore.consoleTaskItem)
  const editingScope = computed(() => mediaStore.editingScope)
  const editingSelectionCount = computed(() => mediaStore.editingSelectionCount)
  const editor = computed(() => mediaStore.editor)
  const editorVideoCodec = computed(() => mediaStore.editorVideoCodec)
  const visibleEncoderProfiles = computed(() => envStore.visibleEncoderProfiles)
  const visibleDecoderProfiles = computed(() =>
    getVisibleDecoderProfiles(envStore.env.checkResult, mediaStore.editorVideoCodec),
  )
  const currentEncoderProfile = computed(() => presetStore.currentEncoderProfile)
  const currentDecoderProfile = computed(() => presetStore.currentDecoderProfile)
  const allSelected = computed(() => mediaStore.allSelected)
  const canStartBatch = computed(() => taskStore.canStartBatch)
  const batchTotal = computed(() => taskStore.batchTotal)
  const globalTaskStatus = computed(() => taskStore.globalTaskStatus)

  // Delegated actions
  async function bootstrap(): Promise<void> {
    if (envStore.env.isBootstrapping) {
      return
    }
    envStore.env.isBootstrapping = true
    try {
      await taskStore.attachTaskListeners()
      const hasPersistedPreset = await presetStore.loadPersistedPreset()
      await envStore.recheckEnvironment(false)
      if (!hasPersistedPreset && envStore.env.checkResult) {
        presetStore.replaceDraftPreset(
          // 通过动态导入避免循环依赖
          (await import('@/lib/task-mapper')).createDefaultWorkbenchPreset(envStore.env.checkResult),
        )
      }
      presetStore.presetPersistenceReady = true
      presetStore.schedulePresetSave()
    } finally {
      envStore.env.isBootstrapping = false
    }
  }

  return {
    // State
    env,
    draftPreset,
    mediaItems,
    activeItemId,
    batch,
    operationIssue,
    // Getters
    selectedIds,
    selectedItems,
    activeItem,
    currentTaskItem,
    batchItems,
    consoleTaskItem,
    editingScope,
    editingSelectionCount,
    editor,
    editorVideoCodec,
    visibleEncoderProfiles,
    visibleDecoderProfiles,
    currentEncoderProfile,
    currentDecoderProfile,
    allSelected,
    canStartBatch,
    batchTotal,
    globalTaskStatus,
    // Actions
    bootstrap,
    recheckEnvironment: envStore.recheckEnvironment,
    clearOperationIssue: envStore.clearOperationIssue,
    setOperationIssue: envStore.setOperationIssue,
    replaceDraftPreset: presetStore.replaceDraftPreset,
    schedulePresetSave: presetStore.schedulePresetSave,
    persistWorkbenchPreset: presetStore.persistWorkbenchPreset,
    loadPersistedPreset: presetStore.loadPersistedPreset,
    normalizeDecodeConfig: presetStore.normalizeDecodeConfig,
    normalizeEncodeConfig: presetStore.normalizeEncodeConfig,
    normalizeDraftPresetProfiles: presetStore.normalizeDraftPresetProfiles,
    patchWorkflow: (mutator: (config: import('@/types').WorkflowConfig) => void) => {
      presetStore.patchWorkflow(mutator)
      mediaStore.forEachEditableItem((item) => {
        const next = cloneWorkflowConfig(item.workflowConfig)
        mutator(next)
        item.workflowConfig = next
      })
    },
    patchDecode: (mutator: (config: import('@/types').DecodeConfig) => void) => {
      presetStore.patchDecode(mutator)
      mediaStore.forEachEditableItem((item) => {
        const next = cloneDecodeConfig(item.decodeConfig)
        mutator(next)
        item.decodeConfig = next
      })
    },
    patchEncode: (mutator: (config: import('@/types').EncodeConfig) => void) => {
      presetStore.patchEncode(mutator)
      mediaStore.forEachEditableItem((item) => {
        const next = cloneEncodeConfig(item.encodeConfig)
        mutator(next)
        item.encodeConfig = next
      })
    },
    patchOutput: (mutator: (config: import('@/types').OutputConfig) => void) => {
      presetStore.patchOutput(mutator)
      mediaStore.forEachEditableItem((item) => {
        const next = cloneOutputConfig(item.outputConfig)
        mutator(next)
        item.outputConfig = next
      })
    },
    setDecodeProfile: presetStore.setDecodeProfile,
    setDecodeHwaccelDevice: presetStore.setDecodeHwaccelDevice,
    setDecodeOption: presetStore.setDecodeOption,
    setEncodeProfile: presetStore.setEncodeProfile,
    setEncodeRateControlMode: presetStore.setEncodeRateControlMode,
    setEncodeRateControlValue: presetStore.setEncodeRateControlValue,
    setEncodeOption: presetStore.setEncodeOption,
    findItem: mediaStore.findItem,
    getEditableTargetIds: mediaStore.getEditableTargetIds,
    forEachEditableItem: mediaStore.forEachEditableItem,
    createMediaItem: mediaStore.createMediaItem,
    normalizeItemProfiles: mediaStore.normalizeItemProfiles,
    inspectMediaItem: mediaStore.inspectMediaItem,
    inspectItems: mediaStore.inspectItems,
    addMediaPaths: mediaStore.addMediaPaths,
    pickInputs: mediaStore.pickInputs,
    setActiveItem: mediaStore.setActiveItem,
    selectAllMedia: mediaStore.selectAllMedia,
    setItemSelected: mediaStore.setItemSelected,
    removeMediaItem: mediaStore.removeMediaItem,
    startBatch: taskStore.startBatch,
    runNextQueuedItem: taskStore.runNextQueuedItem,
    pauseCurrentTask: taskStore.pauseCurrentTask,
    resumeCurrentTask: taskStore.resumeCurrentTask,
    interruptBatch: taskStore.interruptBatch,
    cancelCurrentTask: taskStore.cancelCurrentTask,
    attachTaskListeners: taskStore.attachTaskListeners,
    detachTaskListeners: taskStore.detachTaskListeners,
    handleCurrentTaskCompleted: taskStore.handleCurrentTaskCompleted,
    handleCurrentTaskErrored: taskStore.handleCurrentTaskErrored,
    handleCurrentTaskCancelled: taskStore.handleCurrentTaskCancelled,
    getOptionValue,
    openOutputLocation: async (path?: string) => {
      const { openOutputLocation: invokeOpenOutputLocation } = await import('@/lib/tauri')
      const target =
        path ||
        taskStore.currentTaskItem?.lastOutputPath ||
        taskStore.currentTaskItem?.taskState.outputPath ||
        mediaStore.activeItem?.outputConfig.outputDir ||
        mediaStore.editor.outputConfig.outputDir ||
        ''
      if (!target) {
        return
      }
      try {
        await invokeOpenOutputLocation(target)
        envStore.clearOperationIssue('output')
      } catch (error) {
        envStore.setOperationIssue('output', normalizeError(error, 'open_output_failed'))
      }
    },
    pickOutputDirectory: async () => {
      const { pickOutputDirectory: invokePickOutputDirectory } = await import('@/lib/tauri')
      try {
        const outputDir = await invokePickOutputDirectory()
        envStore.clearOperationIssue('encode')
        if (!outputDir) {
          return
        }
        presetStore.patchOutput((config) => {
          config.outputDir = outputDir
        })
      } catch (error) {
        envStore.setOperationIssue('encode', normalizeError(error, 'pick_output_dir_failed'))
      }
    },
  }
})

function getOptionValue(
  option: { name: string; defaultValue?: import('@/types').CapabilityValue | null; choices: Array<{ value: import('@/types').CapabilityValue }>; type: string },
  values: Record<string, import('@/types').CapabilityValue>,
): import('@/types').CapabilityValue {
  if (option.name in values) {
    return values[option.name] as import('@/types').CapabilityValue
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

function normalizeError(error: unknown, code = 'runtime_error'): import('@/types').TaskError {
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
