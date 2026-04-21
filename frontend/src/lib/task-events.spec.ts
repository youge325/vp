import { describe, expect, it } from 'vitest'
import {
  applyTaskCancelled,
  applyTaskCompleted,
  applyTaskError,
  applyTaskProgress,
  appendTaskLog,
  createIdleTaskState,
} from '@/lib/task-events'

describe('task event reducers', () => {
  it('merges progress payloads', () => {
    const state = applyTaskProgress(createIdleTaskState(), {
      current: 12,
      total: 100,
      percent: 12,
      stage: 'decode',
      stageIndex: 1,
      stageTotal: 2,
    })

    expect(state.status).toBe('running')
    expect(state.current).toBe(12)
    expect(state.stage).toBe('decode')
  })

  it('appends logs and keeps latest entries', () => {
    const state = appendTaskLog(createIdleTaskState(), { message: 'hello' })
    expect(state.logs).toEqual(['hello'])
  })

  it('marks completion and errors', () => {
    const completed = applyTaskCompleted(createIdleTaskState(), {
      outputPath: 'demo.mp4',
      processedFrames: 88,
      timeSeconds: 9.3,
    })
    expect(completed.status).toBe('completed')
    expect(completed.outputPath).toBe('demo.mp4')

    const errored = applyTaskError(createIdleTaskState(), {
      code: 'process_failed',
      message: 'boom',
      details: null,
    })
    expect(errored.status).toBe('error')

    const cancelled = applyTaskCancelled(createIdleTaskState())
    expect(cancelled.status).toBe('cancelled')
    expect(cancelled.error?.code).toBe('cancelled')
  })
})
