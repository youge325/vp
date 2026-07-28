import { computed } from 'vue'
import { displayTaskLogLine } from '@/services/task/events'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import { useConsoleTaskContext } from './useTaskContext'

export function useTaskConsoleState() {
  const mediaStore = useMediaStore()
  const taskStore = useTaskStore()
  const consoleTaskContext = useConsoleTaskContext()

  const logs = computed(() =>
    (consoleTaskContext.value.runState?.taskState.logs ?? []).map(displayTaskLogLine),
  )
  const resumeStatus = computed(
    () => consoleTaskContext.value.runState?.taskState.resumeStatus ?? null,
  )
  const showResumeBanner = computed(() => Boolean(resumeStatus.value?.resumed))
  const done = computed(() => taskStore.batch.completedCount)
  const total = computed(
    () => taskStore.batchRuntimeIds.length || mediaStore.selectedItems.length,
  )
  const progressPercent = computed(() => {
    if (total.value === 0) {
      return 0
    }
    return Math.min(100, Math.round((done.value / total.value) * 100))
  })

  return {
    logs,
    resumeStatus,
    showResumeBanner,
    done,
    total,
    progressPercent,
  }
}
