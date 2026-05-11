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

  it('resetBatch returns to initial state', () => {
    const store = useTaskStore()
    store.setBatch({ isRunning: true, currentId: 'task-1', completedCount: 5 })
    store.setRuntimeIds(['rt-1'])
    store.setPendingConflict({
      mediaId: 'm',
      outputPath: '/p',
      kind: 'final_exists_only',
      completedChunks: 0,
      completedOutputFrames: 0,
      sidecarSignatureMatch: false,
    })

    store.resetBatch()

    expect(store.batch.isRunning).toBe(false)
    expect(store.batch.currentId).toBeNull()
    expect(store.batch.completedCount).toBe(0)
    expect(store.batchRuntimeIds).toEqual([])
    expect(store.pendingConflict).toBeNull()
  })
})
