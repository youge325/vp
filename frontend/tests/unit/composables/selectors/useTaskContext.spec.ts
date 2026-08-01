import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  useConsoleTaskContext,
  useCurrentTaskContext,
} from '@/composables/selectors/useTaskContext'
import { createMediaItem } from '@/services/media/factory'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import { createIdleTaskState } from '@/services/task/events'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'

describe('task context selectors', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('reactively resolves the current item and its matching run state', () => {
    const item = createMediaItem('D:/video/current.mp4', createDefaultWorkbenchPreset(null))
    useMediaStore().appendItems([item])
    useMediaRunState().setTaskState(item.id, {
      ...createIdleTaskState(),
      status: 'running',
    })
    useTaskStore().dispatchBatch({ type: 'started', ids: [item.id] })
    useTaskStore().dispatchBatch({ type: 'queue-advanced', currentId: item.id, remaining: [] })

    const context = useCurrentTaskContext()

    expect(context.value.item?.id).toBe(item.id)
    expect(context.value.runState?.taskState.status).toBe('running')
  })

  it('returns an empty current context for a stale id even when stale state exists', () => {
    useTaskStore().dispatchBatch({ type: 'started', ids: ['missing-item'] })
    useTaskStore().dispatchBatch({ type: 'queue-advanced', currentId: 'missing-item', remaining: [] })
    useMediaRunState().setTaskState('missing-item', {
      ...createIdleTaskState(),
      status: 'running',
    })

    expect(useCurrentTaskContext().value).toEqual({
      item: null,
      runState: null,
    })
  })

  it('falls the console item and run state back to the active id together', () => {
    const mediaStore = useMediaStore()
    const runStateStore = useMediaRunState()
    const activeItem = createMediaItem('D:/video/active.mp4', createDefaultWorkbenchPreset(null))
    mediaStore.appendItems([activeItem])
    mediaStore.setActive(activeItem.id)
    runStateStore.setTaskState(activeItem.id, {
      ...createIdleTaskState(),
      status: 'running',
      logs: ['active'],
    })
    runStateStore.setTaskState('missing-item', {
      ...createIdleTaskState(),
      status: 'running',
      logs: ['stale'],
    })
    useTaskStore().dispatchBatch({ type: 'started', ids: ['missing-item'] })
    useTaskStore().dispatchBatch({ type: 'queue-advanced', currentId: 'missing-item', remaining: [] })

    const context = useConsoleTaskContext()

    expect(context.value.item?.id).toBe(activeItem.id)
    expect(context.value.runState?.taskState.logs).toEqual(['active'])
  })
})
