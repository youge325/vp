import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useTaskStore } from '@/stores/task'

describe('useTaskStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('setBatch merges partial updates', () => {
    const store = useTaskStore()
    expect(store.batch.isRunning).toBe(false)

    store.setBatch({ isRunning: true, queue: ['a', 'b'] })
    expect(store.batch.isRunning).toBe(true)
    expect(store.batch.queue).toEqual(['a', 'b'])
    expect(store.batch.completedCount).toBe(0) // untouched
  })

  it('setRuntimeIds clones the input array', () => {
    const store = useTaskStore()
    const source = ['x', 'y']
    store.setRuntimeIds(source)
    source.push('z')
    expect(store.batchRuntimeIds).toEqual(['x', 'y'])
  })

  it('setPendingConflict accepts a descriptor and null', () => {
    const store = useTaskStore()
    const descriptor = {
      mediaId: 'media-1',
      outputPath: 'D:/out.mp4',
      kind: 'final_exists_with_resume' as const,
      completedChunks: 2,
      completedOutputFrames: 200,
      sidecarSignatureMatch: true,
    }
    store.setPendingConflict(descriptor)
    expect(store.pendingConflict).toEqual(descriptor)

    store.setPendingConflict(null)
    expect(store.pendingConflict).toBeNull()
  })
})
