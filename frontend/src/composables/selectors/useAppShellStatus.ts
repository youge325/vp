import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'

export function useAppShellStatus() {
  const envStore = useEnvStore()
  return {
    issue: computed(() => envStore.env.issue),
    isChecking: computed(() => envStore.env.isChecking),
    isBootstrapping: computed(() => envStore.env.isBootstrapping),
  }
}
