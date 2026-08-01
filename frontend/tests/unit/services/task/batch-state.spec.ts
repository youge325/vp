import { describe, expect, it } from 'vitest'

import { createInitialBatchState, reduceBatchState } from '@/services/task/batch/state'
import type { BatchState } from '@/types/domain/batch'

const runningState = (): BatchState => reduceBatchState(
  createInitialBatchState(),
  { type: 'started', ids: ['a', 'b'] },
)

describe('batch state reducer', () => {
  it.each([
    ['idle', 'pause', 'idle', null],
    ['idle', 'resume', 'idle', null],
    ['idle', 'cancel', 'idle', null],
    ['running', 'pause', 'running', 'pause'],
    ['running', 'resume', 'running', null],
    ['running', 'cancel', 'cancelling', 'cancel'],
    ['paused', 'pause', 'paused', null],
    ['paused', 'resume', 'paused', 'resume'],
    ['paused', 'cancel', 'cancelling', 'cancel'],
    ['cancelling', 'pause', 'cancelling', null],
    ['cancelling', 'resume', 'cancelling', null],
    ['cancelling', 'cancel', 'cancelling', null],
  ] as const)(
    'transitions %s + %s to %s with pending %s',
    (phase, kind, expectedPhase, expectedPending) => {
      const base: BatchState = {
        phase,
        queue: ['b'],
        currentId: 'a',
        controlPending: null,
      }

      const next = reduceBatchState(base, { type: 'control-requested', kind })

      expect(next.phase).toBe(expectedPhase)
      expect(next.controlPending).toBe(expectedPending)
    },
  )

  it('moves pause, resume and cancel through one success transition', () => {
    const running = runningState()
    const pausing = reduceBatchState(running, { type: 'control-requested', kind: 'pause' })
    const paused = reduceBatchState(pausing, { type: 'control-succeeded', kind: 'pause' })
    const resuming = reduceBatchState(paused, { type: 'control-requested', kind: 'resume' })
    const resumed = reduceBatchState(resuming, { type: 'control-succeeded', kind: 'resume' })
    const cancelling = reduceBatchState(resumed, { type: 'control-requested', kind: 'cancel' })
    const cancelled = reduceBatchState(cancelling, { type: 'control-succeeded', kind: 'cancel' })

    expect(paused.phase).toBe('paused')
    expect(resumed.phase).toBe('running')
    expect(cancelled).toMatchObject({ phase: 'cancelling', queue: [], controlPending: null })
  })

  it('restores the exact immutable snapshot after a control failure', () => {
    const running = runningState()
    const pending = reduceBatchState(running, { type: 'control-requested', kind: 'cancel' })
    const restored = reduceBatchState(pending, {
      type: 'control-failed',
      kind: 'cancel',
      snapshot: running,
    })

    expect(restored).toEqual(running)
    expect(restored).not.toBe(running)
    expect(restored.queue).not.toBe(running.queue)
  })

  it('ignores mismatched stale control results', () => {
    const pausing = reduceBatchState(runningState(), { type: 'control-requested', kind: 'pause' })

    expect(reduceBatchState(pausing, { type: 'control-succeeded', kind: 'resume' })).toBe(pausing)
  })

  it('finishes to idle only after the queue is drained', () => {
    const current = reduceBatchState(runningState(), {
      type: 'queue-advanced',
      currentId: 'a',
      remaining: ['b'],
    })
    const continuing = reduceBatchState(current, { type: 'item-finalized' })
    const last = reduceBatchState(continuing, {
      type: 'queue-advanced',
      currentId: 'b',
      remaining: [],
    })

    expect(continuing).toMatchObject({ phase: 'running', currentId: null, queue: ['b'] })
    expect(reduceBatchState(last, { type: 'item-finalized' })).toEqual(createInitialBatchState())
  })

  // @ts-expect-error Boolean mirrors cannot be represented in BatchState.
  const invalidBooleanState: BatchState = { phase: 'idle', queue: [], currentId: null, controlPending: null, isRunning: true }
  expect(invalidBooleanState.phase).toBe('idle')
})
