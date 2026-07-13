import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'
import { getTaskStatusLabel } from '@/services/format/labels'

export function useCurrentTaskStatusLabel() {
  const mediaStore = useMediaStore()
  const runStateStore = useMediaRunState()
  const taskStore = useTaskStore()

  return computed(() => {
    const currentItem = mediaStore.findItem(taskStore.batch.currentId)
    const currentStatus = runStateStore.getByItemId(currentItem?.id)?.taskState.status ?? null
    return getTaskStatusLabel(taskStore.batch, currentStatus)
  })
}
