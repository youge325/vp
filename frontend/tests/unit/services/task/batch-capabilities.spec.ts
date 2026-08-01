import { describe, expect, it, vi } from 'vitest'
import { createConflictResolver } from '@/services/task/batch/conflict'
import type {
  ConflictCapability,
  FinalizationCapability,
  QueueContinuation,
  TaskContextCapability,
} from '@/services/task/batch/lifecycle/types'

type ConflictDeps = Parameters<typeof createConflictResolver>[0]
type ConflictLifecycle = Parameters<typeof createConflictResolver>[1]

const deps: ConflictDeps = {
  getBatch: () => ({
    phase: 'idle',
    queue: [],
    currentId: null,
    controlPending: null,
  }),
  dispatchBatch: vi.fn(),
  setPendingConflict: vi.fn(),
  getMediaItem: () => null,
}

const taskContext: TaskContextCapability = {
  getCurrentTaskContext: () => ({ item: null, runState: null }),
}
const queue: Pick<QueueContinuation, 'launchCurrentItem'> = {
  launchCurrentItem: vi.fn(),
}
const finalization: Pick<FinalizationCapability, 'finalizeCurrent'> = {
  finalizeCurrent: vi.fn(),
}
const lifecycle: ConflictLifecycle = { ...taskContext, ...queue, ...finalization }

// @ts-expect-error Conflict resolution must not depend on queue-wide start.
const leakedQueueCapability: ConflictLifecycle = { ...lifecycle, start: vi.fn() }
// @ts-expect-error Conflict resolution must not gain terminal error handling.
const leakedFinalizationCapability: ConflictLifecycle = { ...lifecycle, handleErrored: vi.fn() }

describe('batch consumer-owned capabilities', () => {
  it('constructs conflict handling from only context, launch and finalization ports', () => {
    const conflict: ConflictCapability = createConflictResolver(deps, lifecycle)

    expect(Object.keys(conflict).sort()).toEqual(['resolveConflict', 'tryStashFromError'])
    expect(Object.keys(lifecycle).sort()).toEqual([
      'finalizeCurrent',
      'getCurrentTaskContext',
      'launchCurrentItem',
    ])
    expect(Object.keys(leakedQueueCapability)).toContain('start')
    expect(Object.keys(leakedFinalizationCapability)).toContain('handleErrored')
  })
})
