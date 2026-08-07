// Pure immutable batch state machine. All lifecycle mutations enter through
// a domain event so invalid boolean combinations cannot be represented.

import type { BatchEvent, BatchState } from '@/types/domain/batch'

export function createInitialBatchState(): BatchState {
  return {
    phase: 'idle',
    queue: [],
    currentId: null,
    controlPending: null,
    runtimeIds: [],
  }
}

export function cloneBatchState(state: BatchState): BatchState {
  switch (state.phase) {
    case 'idle':
      return { ...state, queue: [] }
    case 'running':
    case 'paused':
      return { ...state, queue: [...state.queue] }
    case 'cancelling':
      return { ...state, queue: [] }
  }
}

function idleAfter(state: BatchState): BatchState {
  return {
    phase: 'idle',
    queue: [],
    currentId: null,
    controlPending: null,
    runtimeIds: state.runtimeIds,
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
        runtimeIds: [...event.ids],
      }
    case 'queue-advanced':
      if (state.phase !== 'running' || state.controlPending !== null) {
        return state
      }
      return {
        ...state,
        queue: [...event.remaining],
        currentId: event.currentId,
      }
    case 'queue-cleared':
      if (state.phase === 'running' || state.phase === 'paused') {
        return { ...state, queue: [] }
      }
      return state
    case 'item-finalized':
      if (state.queue.length > 0) {
        return {
          phase: 'running',
          queue: [...state.queue],
          currentId: null,
          controlPending: null,
          runtimeIds: state.runtimeIds,
        }
      }
      return idleAfter(state)
    case 'control-requested': {
      if (state.controlPending !== null) {
        return state
      }
      if (event.kind === 'pause' && state.phase === 'running') {
        return { ...state, controlPending: 'pause' }
      }
      if (event.kind === 'resume' && state.phase === 'paused') {
        return { ...state, controlPending: 'resume' }
      }
      if (event.kind === 'cancel' && (state.phase === 'running' || state.phase === 'paused')) {
        return {
          phase: 'cancelling',
          queue: [],
          currentId: state.currentId,
          controlPending: 'cancel',
          runtimeIds: state.runtimeIds,
        }
      }
      return state
    }
    case 'control-succeeded':
      if (state.controlPending !== event.kind) {
        return state
      }
      if (state.phase === 'running' && event.kind === 'pause') {
        return { ...state, phase: 'paused', controlPending: null }
      }
      if (state.phase === 'paused' && event.kind === 'resume') {
        return { ...state, phase: 'running', controlPending: null }
      }
      if (state.phase === 'cancelling' && event.kind === 'cancel') {
        return { ...state, controlPending: null }
      }
      return state
    case 'control-failed':
      if (state.controlPending !== event.kind) {
        return state
      }
      return cloneBatchState(event.snapshot)
  }
}
