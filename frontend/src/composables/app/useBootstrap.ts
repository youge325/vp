// 应用层 — 应用启动编排:绑定到 App.vue 的生命周期,完成 listener 与初始化。

import { onBeforeUnmount, onMounted } from 'vue'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { useEnvironmentChecker } from './useEnvironmentChecker'
import { usePresetSync } from './usePresetSync'
import { useTaskOrchestrator } from './useTaskOrchestrator'

export function useBootstrap() {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()
  const { recheckEnvironment } = useEnvironmentChecker()
  const { loadPersistedPreset, startAutoSync } = usePresetSync()
  const { attachTaskListeners, detachTaskListeners } = useTaskOrchestrator()

  onMounted(async () => {
    envStore.setBootstrapping(true)
    try {
      // Step 1 — listener binding (hard-fail if this breaks)
      await attachTaskListeners()

      // Step 2 — preset loading (soft-fail, falls back to defaults)
      const presetOk = await loadPersistedPreset().then(() => true).catch((error: unknown) => {
        console.warn('Preset load failed, using defaults:', error)
        return false
      })

      // Step 3 — environment check (soft-fail)
      await recheckEnvironment(false).catch((error: unknown) => {
        console.warn('Environment check failed:', error)
      })

      // Step 4 — start auto-sync only if preset loaded successfully
      if (presetOk) {
        startAutoSync()
      }
    } finally {
      presetStore.setPersistenceReady(true)
      envStore.setBootstrapping(false)
    }
  })

  onBeforeUnmount(() => {
    detachTaskListeners()
  })
}
