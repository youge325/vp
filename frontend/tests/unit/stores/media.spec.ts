import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useMediaStore } from '@/stores/media'
import { createMediaItem } from '@/services/media/factory'
import { createTestPreset } from '../fixtures/preset'

describe('useMediaStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('appendItems promotes the first appended item as active', () => {
    const store = useMediaStore()
    const a = createMediaItem('/a.mp4', createTestPreset())
    const b = createMediaItem('/b.mp4', createTestPreset())

    store.appendItems([a, b])

    expect(store.mediaItems).toHaveLength(2)
    expect(store.activeItemId).toBe(a.id)
  })

  it('appendItems with empty array is a no-op', () => {
    const store = useMediaStore()
    store.appendItems([])
    expect(store.mediaItems).toHaveLength(0)
    expect(store.activeItemId).toBeNull()
  })

  it('removeItem moves activeItemId forward when removing the active item', () => {
    const store = useMediaStore()
    const a = createMediaItem('/a.mp4', createTestPreset())
    const b = createMediaItem('/b.mp4', createTestPreset())
    store.appendItems([a, b])

    store.removeItem(a.id)

    expect(store.mediaItems).toHaveLength(1)
    expect(store.activeItemId).toBe(b.id)
  })

  it('selectAll toggles every item', () => {
    const store = useMediaStore()
    const a = createMediaItem('/a.mp4', createTestPreset())
    const b = createMediaItem('/b.mp4', createTestPreset())
    store.appendItems([a, b])

    store.selectAll(false)
    expect(store.mediaItems.every((item) => !item.selected)).toBe(true)

    store.selectAll(true)
    expect(store.allSelected).toBe(true)
  })

})
