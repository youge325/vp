// 应用层 — 预设持久化协调:加载、保存、debounce、自动同步草稿变更。

import { watch } from 'vue'
import type { WorkbenchPreset } from '@/types/protocol'
import { TASK_ERROR_CODES } from '@/types/protocol'
import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'
import { usePresetStore } from '@/stores/preset'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
import { normalizeError } from '@/lib/errors/normalize'
import { cloneWorkbenchPreset } from '@/services/preset/clone'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'

const PRESET_SAVE_DEBOUNCE_MS = 300

interface PresetSaveRequest {
  generation: number
  preset: WorkbenchPreset
}

export function usePresetSync() {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()
  const issueStore = useIssueStore()
  let saveTimer: ReturnType<typeof setTimeout> | null = null
  let latestSaveGeneration = 0
  let queuedSave: PresetSaveRequest | null = null
  let saveInFlight = false

  function handlePersistenceFailure(
    error: unknown,
    fallbackMessage: string,
    resetDraft: boolean,
  ): void {
    const normalized = normalizeError(error, TASK_ERROR_CODES.PersistenceFailed)
    if (normalized.code === TASK_ERROR_CODES.SchemaMismatch) {
      recoverFromSchemaMismatch()
      return
    }
    if (resetDraft) {
      presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
    }
    issueStore.setIssue('preset', {
      ...normalized,
      message: normalized.message || fallbackMessage,
    })
  }

  function recoverFromSchemaMismatch(): WorkbenchPreset {
    const recovered = createDefaultWorkbenchPreset(envStore.env.checkResult)
    presetStore.replaceDraftPreset(recovered)
    issueStore.setIssue('preset', {
      code: TASK_ERROR_CODES.SchemaMismatch,
      message: 'Stored workbench preset is from an incompatible version. The editor has been reset to defaults.',
      details: null,
    })
    return recovered
  }

  async function drainSaveQueue(): Promise<void> {
    if (saveInFlight) {
      return
    }
    saveInFlight = true

    try {
      while (queuedSave) {
        const request = queuedSave
        queuedSave = null
        if (request.generation !== latestSaveGeneration) {
          continue
        }
        try {
          await presetIpc.save(request.preset)
          if (request.generation === latestSaveGeneration) {
            issueStore.clearIssue('preset')
          }
        } catch (error) {
          if (request.generation === latestSaveGeneration) {
            handlePersistenceFailure(error, 'Unable to save the workbench preset.', false)
          }
        }
      }
    } finally {
      saveInFlight = false
      if (queuedSave) {
        void drainSaveQueue()
      }
    }
  }

  function scheduleSave(): void {
    if (!presetStore.presetPersistenceReady) {
      return
    }
    if (saveTimer) {
      clearTimeout(saveTimer)
    }
    const generation = ++latestSaveGeneration
    saveTimer = setTimeout(() => {
      saveTimer = null
      if (generation !== latestSaveGeneration) {
        return
      }
      queuedSave = {
        generation,
        preset: cloneWorkbenchPreset(presetStore.draftPreset),
      }
      void drainSaveQueue()
    }, PRESET_SAVE_DEBOUNCE_MS)
  }

  async function loadPersistedPreset(): Promise<void> {
    try {
      const preset = await presetIpc.load()
      if (!preset) {
        presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
        return
      }
      presetStore.replaceDraftPreset(cloneWorkbenchPreset(preset))
      issueStore.clearIssue('preset')
    } catch (error) {
      const normalized = normalizeError(error, TASK_ERROR_CODES.PersistenceFailed)
      if (normalized.code === TASK_ERROR_CODES.SchemaMismatch) {
        const recovered = recoverFromSchemaMismatch()
        try {
          await presetIpc.save(cloneWorkbenchPreset(recovered))
        } catch (rebuildError) {
          const rebuildFailure = normalizeError(
            rebuildError,
            TASK_ERROR_CODES.PersistenceFailed,
          )
          issueStore.setIssue('preset', {
            ...rebuildFailure,
            message: `The incompatible preset was isolated, but its default replacement could not be saved: ${rebuildFailure.message}`,
          })
        }
        return
      }
      handlePersistenceFailure(error, 'Unable to load the saved workbench preset.', true)
    }
  }

  function startAutoSync(): void {
    watch(
      () => [presetStore.draftPreset.decodeConfig, presetStore.draftPreset.encodeConfig, presetStore.draftPreset.workflowConfig, presetStore.draftPreset.outputConfig],
      () => scheduleSave(),
      { deep: true },
    )
  }

  return {
    loadPersistedPreset,
    startAutoSync,
  }
}
