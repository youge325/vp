import { describe, expect, it } from 'vitest'
import { createMediaItem } from '@/services/media/factory'
import { createIdleTaskState } from '@/services/task/events'
import { createTestPreset } from '../../fixtures/preset'

describe('createMediaItem identity', () => {
  it('generates a non-empty id for each media item', () => {
    const item = createMediaItem('/path/to/video.mp4', createTestPreset())
    expect(typeof item.id).toBe('string')
    expect(item.id.length).toBeGreaterThan(0)
  })

  it('generates unique ids for separate media items', () => {
    const first = createMediaItem('/a.mp4', createTestPreset())
    const second = createMediaItem('/b.mp4', createTestPreset())
    expect(first.id).not.toBe(second.id)
  })

  it('uses the filename portion of the input path as the display name', () => {
    expect(createMediaItem('/path/to/video.mp4', createTestPreset()).displayName).toBe('video.mp4')
    expect(createMediaItem('video.mp4', createTestPreset()).displayName).toBe('video.mp4')
  })
})

describe('createIdleTaskState', () => {
  it('returns idle state with empty logs', () => {
    const state = createIdleTaskState()
    expect(state.status).toBe('idle')
    expect(state.logs).toEqual([])
    expect(state.resumeStatus).toBeNull()
  })

})

describe('createMediaItem', () => {
  it('creates a media item from path and preset', () => {
    const item = createMediaItem('/path/to/video.mp4', createTestPreset())
    expect(item.inputPath).toBe('/path/to/video.mp4')
    expect(item.displayName).toBe('video.mp4')
    expect(item.selected).toBe(true)
    expect(item.decodeConfig.mode).toBe('software')
  })

})
