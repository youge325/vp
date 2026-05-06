// 应用层 — 预设持久化协调:加载、保存、debounce、自动同步草稿变更。

import { watch } from 'vue'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { WorkbenchPreset } from '@/types/protocol'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
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
  let saveTimer: ReturnType<typeof setTimeout> | null = null

  async function persistDraft(): Promise<void> {
    try {
      await presetIpc.save(cloneWorkbenchPreset(presetStore.draftPreset))
    } catch {
      // 忽略持久化失败,保留内存中的编辑器可用。
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

  async function loadPersistedPreset(): Promise<boolean> {
    try {
      const preset = await presetIpc.load()
      if (!preset) {
        presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
        return false
      }
      presetStore.replaceDraftPreset(coercePreset(preset, envStore.env.checkResult))
      return true
    } catch {
      presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
      return false
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
    persistDraft,
    scheduleSave,
    loadPersistedPreset,
    startAutoSync,
  }
}
