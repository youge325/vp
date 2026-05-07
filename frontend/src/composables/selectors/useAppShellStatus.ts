import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { getTaskStatusLabel } from '@/services/format/labels'

export function useAppShellStatus() {
  const envStore = useEnvStore()
  const { batch, currentTaskItem } = useTaskOrchestrator()
  return {
    issue: computed(() => envStore.env.issue),
    isChecking: computed(() => envStore.env.isChecking),
    isBootstrapping: computed(() => envStore.env.isBootstrapping),
    topbarStatus: computed(() =>
      getTaskStatusLabel(batch, currentTaskItem.value?.taskState.status ?? null),
    ),
  }
}
