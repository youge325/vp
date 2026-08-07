import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useTaskStore } from '@/stores/task'

describe('useTaskStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('dispatchBatch applies immutable domain transitions', () => {
    const store = useTaskStore()
    expect(store.batch.phase).toBe('idle')

    store.dispatchBatch({ type: 'started', ids: ['a', 'b'] })
    expect(store.batch.phase).toBe('running')
    expect(store.batch.queue).toEqual(['a', 'b'])

    store.dispatchBatch({ type: 'queue-advanced', currentId: 'a', remaining: ['b'] })
    expect(store.batch.currentId).toBe('a')
    expect(store.batch.queue).toEqual(['b'])
  })

  it('started is the only transition that replaces cloned runtime ids', () => {
    const store = useTaskStore()
    const source = ['x', 'y']
    store.dispatchBatch({ type: 'started', ids: source })
    source.push('z')
    expect(store.batch.runtimeIds).toEqual(['x', 'y'])
  })

  it('setPendingConflict accepts a descriptor and null', () => {
    const store = useTaskStore()
    const descriptor = {
      outputPath: 'D:/out.mp4',
      kind: 'final_exists_with_resume' as const,
      progress: {
        completedChunks: 2,
        completedOutputFrames: 200,
        totalOutputFrames: 400,
      },
    }
    store.setPendingConflict(descriptor)
    expect(store.pendingConflict).toEqual(descriptor)

    store.setPendingConflict(null)
    expect(store.pendingConflict).toBeNull()
  })
})
