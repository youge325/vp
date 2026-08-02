// 应用层 — 应用启动编排:绑定到 App.vue 的生命周期,完成 listener 与初始化。

import { onBeforeUnmount, onMounted } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'
import { usePresetStore } from '@/stores/preset'
import { normalizeError } from '@/lib/errors/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol'
import { useEnvironmentChecker } from './useEnvironmentChecker'
import { usePresetSync } from './usePresetSync'
import { attachTaskListeners, disposeRunner } from './taskOrchestratorRuntime'

export function useBootstrap() {
  const envStore = useEnvStore()
  const issueStore = useIssueStore()
  const presetStore = usePresetStore()
  const { checkEnvironment } = useEnvironmentChecker()
  const { loadPersistedPreset, startAutoSync, dispose: disposePresetSync } = usePresetSync()
  let generation = 0

  const isActive = (candidate: number): boolean => candidate === generation

  onMounted(async () => {
    const activeGeneration = ++generation
    let listenersAttached = false
    envStore.setBootstrapping(true)
    presetStore.setPersistenceReady(false)
    try {
      // Step 1 — listener binding (hard-fail if this breaks)
      await attachTaskListeners()
      if (!isActive(activeGeneration)) {
        return
      }
      listenersAttached = true

      // Step 2 — expected load failures fall back internally; only an
      // unexpected exception prevents the autosync watcher from starting.
      const presetSyncReady = await loadPersistedPreset().then(() => true).catch((error: unknown) => {
        console.warn('Preset load failed, using defaults:', error)
        return false
      })
      if (!isActive(activeGeneration)) {
        return
      }

      // Step 3 — environment check (soft-fail)
      await checkEnvironment({
        forceRefresh: false,
        isActive: () => isActive(activeGeneration),
      })
      if (!isActive(activeGeneration)) {
        return
      }

      // Step 4 — start auto-sync once preset loading has settled.
      if (presetSyncReady) {
        startAutoSync()
      }
    } catch (error: unknown) {
      if (isActive(activeGeneration)) {
        issueStore.setIssue('task', normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
      }
    } finally {
      if (isActive(activeGeneration)) {
        presetStore.setPersistenceReady(listenersAttached)
        envStore.setBootstrapping(false)
      }
    }
  })

  onBeforeUnmount(() => {
    generation += 1
    disposePresetSync()
    // Detach listeners and drop the cached runner so a later mount
    // cannot reuse an instance bound to discarded Pinia stores.
    disposeRunner()
    presetStore.setPersistenceReady(false)
    envStore.setChecking(false)
    envStore.setBootstrapping(false)
  })
}
