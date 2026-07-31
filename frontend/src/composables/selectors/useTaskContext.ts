import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'
import {
  resolveConsoleTaskContext,
  resolveTaskContext,
  type TaskContextPort,
} from '@/services/task/task-context'

function useTaskContextLookup() {
  const mediaStore = useMediaStore()
  const runStateStore = useMediaRunState()
  const lookup: TaskContextPort = {
    getMediaItem: (id) => mediaStore.findItem(id),
    getItemRunState: (id) => runStateStore.getByItemId(id),
  }
  return { lookup, mediaStore, taskStore: useTaskStore() }
}

export function useCurrentTaskContext() {
  const { lookup, taskStore } = useTaskContextLookup()
  return computed(() => resolveTaskContext(lookup, taskStore.batch.currentId))
}

export function useConsoleTaskContext() {
  const { lookup, mediaStore, taskStore } = useTaskContextLookup()
  return computed(() =>
    resolveConsoleTaskContext(lookup, taskStore.batch.currentId, mediaStore.activeItemId),
  )
}
