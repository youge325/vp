import { describe, expect, it } from 'vitest'
import { TERMINAL_PROGRESS_PREFIX } from '@/types'
import {
  applyTaskCancelled,
  applyTaskCancelling,
  applyTaskCompleted,
  applyTaskError,
  applyTaskPaused,
  applyTaskProgress,
  applyTaskResumed,
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

  it('tracks paused, resumed, and cancelling states', () => {
    const running = applyTaskProgress(createIdleTaskState(), {
      current: 24,
      total: 100,
      percent: 24,
      stage: 'encode',
      stageIndex: 1,
      stageTotal: 2,
    })
    const paused = applyTaskPaused(running)
    const bufferedProgress = applyTaskProgress(paused, {
      current: 25,
      total: 100,
      percent: 25,
      stage: 'encode',
      stageIndex: 1,
      stageTotal: 2,
    })
    const resumed = applyTaskResumed(paused)
    const cancelling = applyTaskCancelling(resumed)

    expect(paused.status).toBe('paused')
    expect(bufferedProgress.status).toBe('paused')
    expect(bufferedProgress.percent).toBe(25)
    expect(resumed.status).toBe('running')
    expect(cancelling.status).toBe('cancelling')
  })

  it('appends logs and keeps latest entries', () => {
    const state = appendTaskLog(createIdleTaskState(), { message: 'hello' })
    expect(state.logs).toEqual(['hello'])
  })

  it('replaces the active CLI progress line instead of appending duplicates', () => {
    const initial = createIdleTaskState()
    const first = appendTaskLog(initial, { message: `${TERMINAL_PROGRESS_PREFIX} 10%` })
    const second = appendTaskLog(first, { message: `${TERMINAL_PROGRESS_PREFIX} 20%` })
    const final = appendTaskLog(second, { message: 'encoder ready' })

    expect(second.logs).toEqual([`${TERMINAL_PROGRESS_PREFIX} 20%`])
    expect(final.logs).toEqual([`${TERMINAL_PROGRESS_PREFIX} 20%`, 'encoder ready'])
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
