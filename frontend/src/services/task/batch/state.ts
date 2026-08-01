// Pure immutable batch state machine. All lifecycle mutations enter through
// a domain event so invalid boolean combinations cannot be represented.

import type { BatchEvent, BatchState } from '@/types/domain/batch'

export function createInitialBatchState(): BatchState {
  return {
    phase: 'idle',
    queue: [],
    currentId: null,
    controlPending: null,
  }
}

function snapshot(state: BatchState): BatchState {
  return {
    ...state,
    queue: [...state.queue],
  }
}

export function reduceBatchState(state: BatchState, event: BatchEvent): BatchState {
  switch (event.type) {
    case 'started':
      if (state.phase !== 'idle' || event.ids.length === 0) {
        return state
      }
      return {
        phase: 'running',
        queue: [...event.ids],
        currentId: null,
        controlPending: null,
      }
    case 'queue-advanced':
      return {
        phase: 'running',
        queue: [...event.remaining],
        currentId: event.currentId,
        controlPending: null,
      }
    case 'queue-cleared':
      return { ...state, queue: [] }
    case 'item-finalized':
      if (state.queue.length > 0) {
        return {
          ...state,
          phase: 'running',
          currentId: null,
          controlPending: null,
        }
      }
      return createInitialBatchState()
    case 'control-requested': {
      if (state.controlPending !== null) {
        return state
      }
      const valid = event.kind === 'pause'
        ? state.phase === 'running'
        : event.kind === 'resume'
          ? state.phase === 'paused'
          : state.phase === 'running' || state.phase === 'paused'
      if (!valid) {
        return state
      }
      return {
        ...state,
        phase: event.kind === 'cancel' ? 'cancelling' : state.phase,
        queue: event.kind === 'cancel' ? [] : state.queue,
        controlPending: event.kind,
      }
    }
    case 'control-succeeded':
      if (state.controlPending !== event.kind) {
        return state
      }
      return {
        ...state,
        phase: event.kind === 'pause'
          ? 'paused'
          : event.kind === 'resume'
            ? 'running'
            : 'cancelling',
        controlPending: null,
      }
    case 'control-failed':
      if (state.controlPending !== event.kind) {
        return state
      }
      return snapshot(event.snapshot)
  }
}
