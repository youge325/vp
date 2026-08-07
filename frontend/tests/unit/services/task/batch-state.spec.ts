import { describe, expect, it } from 'vitest'

import { createInitialBatchState, reduceBatchState } from '@/services/task/batch/state'
import type { BatchPhase, BatchState } from '@/types/domain/batch'

function runningState(): BatchState {
  const started = reduceBatchState(
    createInitialBatchState(),
    { type: 'started', ids: ['a', 'b'] },
  )
  return reduceBatchState(started, {
    type: 'queue-advanced',
    currentId: 'a',
    remaining: ['b'],
  })
}

function stateForPhase(phase: BatchPhase): BatchState {
  const running = runningState()
  if (phase === 'idle') {
    return createInitialBatchState()
  }
  if (phase === 'running') {
    return running
  }
  if (phase === 'paused') {
    const pending = reduceBatchState(running, { type: 'control-requested', kind: 'pause' })
    return reduceBatchState(pending, { type: 'control-succeeded', kind: 'pause' })
  }
  return reduceBatchState(running, { type: 'control-requested', kind: 'cancel' })
}

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
    ['cancelling', 'pause', 'cancelling', 'cancel'],
    ['cancelling', 'resume', 'cancelling', 'cancel'],
    ['cancelling', 'cancel', 'cancelling', 'cancel'],
  ] as const)(
    'transitions %s + %s to %s with pending %s',
    (phase, kind, expectedPhase, expectedPending) => {
      const next = reduceBatchState(stateForPhase(phase), { type: 'control-requested', kind })

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
    expect(restored.runtimeIds).toBe(running.runtimeIds)
  })

  it('ignores mismatched stale control results', () => {
    const pausing = reduceBatchState(runningState(), { type: 'control-requested', kind: 'pause' })

    expect(reduceBatchState(pausing, { type: 'control-succeeded', kind: 'resume' })).toBe(pausing)
  })

  it('preserves completed runtime ids after the queue drains and replaces them on the next start', () => {
    const current = runningState()
    const continuing = reduceBatchState(current, { type: 'item-finalized' })
    const last = reduceBatchState(continuing, {
      type: 'queue-advanced',
      currentId: 'b',
      remaining: [],
    })
    const completed = reduceBatchState(last, { type: 'item-finalized' })

    expect(continuing).toMatchObject({ phase: 'running', currentId: null, queue: ['b'] })
    expect(completed).toMatchObject({
      phase: 'idle',
      currentId: null,
      runtimeIds: ['a', 'b'],
    })
    expect(reduceBatchState(completed, { type: 'started', ids: ['next'] }).runtimeIds)
      .toEqual(['next'])
  })

  it('rejects illegal phase and control combinations at compile time', () => {
    // @ts-expect-error Idle batches cannot retain a current task.
    const invalidIdle: BatchState = { phase: 'idle', queue: [], currentId: 'a', controlPending: null, runtimeIds: ['a'] }
    // @ts-expect-error Running batches cannot have a resume request pending.
    const invalidRunning: BatchState = { phase: 'running', queue: [], currentId: 'a', controlPending: 'resume', runtimeIds: ['a'] }
    // @ts-expect-error Paused batches cannot have a pause request pending.
    const invalidPaused: BatchState = { phase: 'paused', queue: [], currentId: 'a', controlPending: 'pause', runtimeIds: ['a'] }
    // @ts-expect-error Cancelling batches cannot retain queued work.
    const invalidCancelling: BatchState = { phase: 'cancelling', queue: ['b'], currentId: 'a', controlPending: 'cancel', runtimeIds: ['a', 'b'] }

    expect([
      invalidIdle.phase,
      invalidRunning.phase,
      invalidPaused.phase,
      invalidCancelling.phase,
    ]).toEqual(['idle', 'running', 'paused', 'cancelling'])
  })
})
