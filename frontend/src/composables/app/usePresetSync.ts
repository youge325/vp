// 应用层 — 预设持久化协调:加载、保存、debounce、自动同步草稿变更。

import { watch } from 'vue'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { WorkbenchPreset } from '@/types/protocol'
import { TASK_ERROR_CODES } from '@/types/protocol'
import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'
import { usePresetStore } from '@/stores/preset'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
import { normalizeError } from '@/services/error/normalize'
import {
  cloneDecodeConfig,
  cloneEncodeConfig,
  cloneOutputConfig,
  cloneWorkbenchPreset,
  cloneWorkflowConfig,
} from '@/services/preset/clone'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'

const PRESET_SAVE_DEBOUNCE_MS = 300

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

export function usePresetSync() {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()
  const issueStore = useIssueStore()
  let saveTimer: ReturnType<typeof setTimeout> | null = null

  function reportPresetIssue(error: unknown, fallbackMessage: string): void {
    const normalized = normalizeError(error, TASK_ERROR_CODES.PersistenceFailed)
    issueStore.setIssue('preset', {
      ...normalized,
      message: normalized.message || fallbackMessage,
    })
  }

  function recoverFromSchemaMismatch(): void {
    presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
    issueStore.setIssue('preset', {
      code: TASK_ERROR_CODES.SchemaMismatch,
      message: 'Stored workbench preset is from an incompatible version. The editor has been reset to defaults.',
      details: null,
    })
  }

  async function persistDraft(): Promise<void> {
    try {
      await presetIpc.save(cloneWorkbenchPreset(presetStore.draftPreset))
      // Clear any prior preset-scoped error once a write succeeds.
      issueStore.clearIssue('preset')
    } catch (error) {
      const normalized = normalizeError(error, TASK_ERROR_CODES.PersistenceFailed)
      if (normalized.code === TASK_ERROR_CODES.SchemaMismatch) {
        recoverFromSchemaMismatch()
        return
      }
      reportPresetIssue(error, 'Unable to save the workbench preset.')
    }
  }

  function scheduleSave(): void {
    if (!presetStore.presetPersistenceReady) {
      return
    }
    if (saveTimer) {
      clearTimeout(saveTimer)
    }
    saveTimer = setTimeout(() => {
      saveTimer = null
      void persistDraft()
    }, PRESET_SAVE_DEBOUNCE_MS)
  }

  async function loadPersistedPreset(): Promise<void> {
    try {
      const preset = await presetIpc.load()
      if (!preset) {
        presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
        return
      }
      presetStore.replaceDraftPreset(coercePreset(preset, envStore.env.checkResult))
      issueStore.clearIssue('preset')
    } catch (error) {
      const normalized = normalizeError(error, TASK_ERROR_CODES.PersistenceFailed)
      if (normalized.code === TASK_ERROR_CODES.SchemaMismatch) {
        recoverFromSchemaMismatch()
        return
      }
      presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
      reportPresetIssue(error, 'Unable to load the saved workbench preset.')
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
