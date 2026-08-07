import { computed } from 'vue'
import { displayTaskLogLine } from '@/services/task/events'
import {
  resolveConsoleTaskContext,
  type TaskContextPort,
} from '@/services/task/task-context'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'

export function useTaskConsoleState() {
  const mediaStore = useMediaStore()
  const mediaRunState = useMediaRunState()
  const taskStore = useTaskStore()
  const lookup: TaskContextPort = {
    getMediaItem: (id) => mediaStore.findItem(id),
    getItemRunState: (id) => mediaRunState.getByItemId(id),
  }
  const consoleTaskContext = computed(() =>
    resolveConsoleTaskContext(lookup, taskStore.batch.currentId, mediaStore.activeItemId),
  )

  const logs = computed(() =>
    (consoleTaskContext.value.runState?.taskState.logs ?? []).map(displayTaskLogLine),
  )
  const resumeStatus = computed(
    () => consoleTaskContext.value.runState?.taskState.resumeStatus ?? null,
  )
  const showResumeBanner = computed(() => Boolean(resumeStatus.value?.resumed))
  const done = computed(() => taskStore.batchRuntimeIds.filter(
    (id) => mediaRunState.getByItemId(id)?.taskState.status === 'completed',
  ).length)
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
