import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useCurrentTaskStatusLabel } from '@/composables/selectors/useCurrentTaskStatusLabel'
import { createMediaItem } from '@/services/media/factory'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import { createIdleTaskState } from '@/services/task/events'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { useTaskStore } from '@/stores/task'

describe('useCurrentTaskStatusLabel', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  function appendCurrentItem() {
    const mediaStore = useMediaStore()
    const item = createMediaItem('D:/video/input.mp4', createDefaultWorkbenchPreset(null))
    mediaStore.appendItems([item])
    useTaskStore().setBatch({ currentId: item.id })
    return item
  }

  it('returns idle when no task is running', () => {
    expect(useCurrentTaskStatusLabel().value).toBe('idle')
  })

  it('returns the running state for the current media item', () => {
    const item = appendCurrentItem()
    useTaskStore().setBatch({ isRunning: true })
    useMediaRunState().setTaskState(item.id, {
      ...createIdleTaskState(),
      status: 'running',
    })

    expect(useCurrentTaskStatusLabel().value).toBe('running')
  })

  it('preserves the paused state for the current media item', () => {
    const item = appendCurrentItem()
    useTaskStore().setBatch({ isRunning: true, isPaused: true })
    useMediaRunState().setTaskState(item.id, {
      ...createIdleTaskState(),
      status: 'paused',
    })

    expect(useCurrentTaskStatusLabel().value).toBe('paused')
  })

  it('ignores stale run state when the current media id no longer exists', () => {
    useTaskStore().setBatch({ currentId: 'missing-item' })
    useMediaRunState().setTaskState('missing-item', {
      ...createIdleTaskState(),
      status: 'paused',
    })

    expect(useCurrentTaskStatusLabel().value).toBe('idle')
  })
})
