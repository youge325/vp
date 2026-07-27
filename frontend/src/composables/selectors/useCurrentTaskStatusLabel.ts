import { computed } from 'vue'
import { useTaskStore } from '@/stores/task'
import { getTaskStatusLabel } from '@/services/format/labels'
import { useCurrentTaskContext } from './useTaskContext'

export function useCurrentTaskStatusLabel() {
  const taskStore = useTaskStore()
  const currentTaskContext = useCurrentTaskContext()

  return computed(() => {
    const currentStatus = currentTaskContext.value.runState?.taskState.status ?? null
    return getTaskStatusLabel(taskStore.batch, currentStatus)
  })
}
