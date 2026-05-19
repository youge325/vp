import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { getTaskStatusLabel } from '@/services/format/labels'

export function useAppShellStatus() {
  const envStore = useEnvStore()
  const runStateStore = useMediaRunState()
  const { batch, currentTaskItem } = useTaskOrchestrator()
  return {
    issue: computed(() => envStore.env.issue),
    isChecking: computed(() => envStore.env.isChecking),
    isBootstrapping: computed(() => envStore.env.isBootstrapping),
    topbarStatus: computed(() =>
      getTaskStatusLabel(
        batch,
        runStateStore.getByItemId(currentTaskItem.value?.id)?.taskState.status ?? null,
      ),
    ),
  }
}
