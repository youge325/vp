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
      await attachTaskListeners()
      await loadPersistedPreset()
      await recheckEnvironment(false)
    } finally {
      presetStore.setPersistenceReady(true)
      envStore.setBootstrapping(false)
      startAutoSync()
    }
  })

  onBeforeUnmount(() => {
    detachTaskListeners()
  })
}
