import { describe, expect, it, vi } from 'vitest'
import { createMediaItem } from '@/services/media/factory'
import { createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import { createIdleTaskState } from '@/services/task/events'
import {
  resolveConsoleTaskContext,
  resolveTaskContext,
} from '@/services/task/task-context'
import type { MediaRunState } from '@/types/domain/media'

function createRunState(log: string): MediaRunState {
  return {
    taskState: { ...createIdleTaskState(), logs: [log] },
    lastOutputPath: '',
  }
}

describe('task context resolver', () => {
  it('pairs an existing media item with the run state from the same id', () => {
    const item = createMediaItem('D:/video/current.mp4', createDefaultWorkbenchPreset(null))
    const runState = createRunState('current')

    expect(resolveTaskContext({
      getMediaItem: (id) => id === item.id ? item : null,
      getItemRunState: (id) => id === item.id ? runState : null,
    }, item.id)).toEqual({ item, runState })
  })

  it('returns null when the media id is stale', () => {
    const getItemRunState = vi.fn(() => createRunState('stale'))

    expect(resolveTaskContext({
      getMediaItem: () => null,
      getItemRunState,
    }, 'missing')).toEqual({ item: null, runState: null })
    expect(getItemRunState).not.toHaveBeenCalled()
  })

  it('falls the entire console context back to the active item', () => {
    const activeItem = createMediaItem('D:/video/active.mp4', createDefaultWorkbenchPreset(null))
    const activeState = createRunState('active')
    const staleState = createRunState('stale')

    expect(resolveConsoleTaskContext({
      getMediaItem: (id) => id === activeItem.id ? activeItem : null,
      getItemRunState: (id) => id === activeItem.id ? activeState : id === 'stale' ? staleState : null,
    }, 'stale', activeItem.id)).toEqual({
      item: activeItem,
      runState: activeState,
    })
  })
})
