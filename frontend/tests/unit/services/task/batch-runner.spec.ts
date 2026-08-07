import { describe, expect, it, vi } from 'vitest'

import { createBatchRunner } from '@/services/task/batch-runner'
import { createInitialBatchState, reduceBatchState } from '@/services/task/batch/state'
import type { BatchRunnerDeps } from '@/services/task/batch/lifecycle/types'
import type { BatchPhase, BatchState } from '@/types/domain/batch'
import type { MediaItem, MediaRunState, MediaTaskState } from '@/types/domain/media'
import { createIdleTaskState } from '@/services/task/events'
import type { TaskRequest } from '@/types/protocol'
import { createDeferred } from '../../fixtures/deferred'
import { createTestPreset } from '../../fixtures/preset'

interface BatchHarness {
  deps: BatchRunnerDeps
  items: Map<string, MediaItem>
  runStates: Map<string, MediaRunState>
  batch: () => BatchState
  activate: (id: string, queue?: string[], phase?: Extract<BatchPhase, 'running' | 'paused'>) => void
}

function makeHarness(overrides: Partial<BatchRunnerDeps> = {}): BatchHarness {
  let batchState = createInitialBatchState()
  const items = new Map<string, MediaItem>()
  const runStates = new Map<string, MediaRunState>()

  const deps: BatchRunnerDeps = {
    startTask: vi.fn().mockResolvedValue(undefined),
    cancelTask: vi.fn().mockResolvedValue(undefined),
    pauseTask: vi.fn().mockResolvedValue(undefined),
    resumeTask: vi.fn().mockResolvedValue(undefined),
    checkResume: vi.fn().mockResolvedValue({
      type: 'resume_inspection',
      pipeline_kind: 'streaming',
      outputPath: '',
      input_path: '',
      finalExists: false,
      sidecarExists: false,
      signatureMatch: false,
      completedChunks: 0,
      completedOutputFrames: 0,
      nextSourceFrame: 0,
      totalOutputFrames: 0,
    }),
    openOutputLocation: vi.fn().mockResolvedValue(undefined),
    getMediaItem: (id) => items.get(id) ?? null,
    getItemRunState: (id) => runStates.get(id) ?? null,
    setItemTaskState: (id, state: MediaTaskState) => {
      const existing = runStates.get(id) ?? { taskState: createIdleTaskState(), lastOutputPath: '' }
      runStates.set(id, { ...existing, taskState: state })
    },
    setTaskIssue: vi.fn(),
    setItemLastOutputPath: (id, path) => {
      const existing = runStates.get(id) ?? { taskState: createIdleTaskState(), lastOutputPath: '' }
      runStates.set(id, { ...existing, lastOutputPath: path })
    },
    resetItemRunState: (id) => {
      runStates.set(id, { taskState: createIdleTaskState(), lastOutputPath: '' })
    },
    setActiveItem: vi.fn(),
    getActiveItemId: () => null,
    getBatch: () => batchState,
    dispatchBatch: (event) => {
      batchState = reduceBatchState(batchState, event)
    },
    setPendingConflict: vi.fn(),
    buildRequest: (item) => ({
      inputPath: item.inputPath,
      decodeConfig: item.decodeConfig,
      workflowConfig: item.workflowConfig,
      encodeConfig: item.encodeConfig,
      outputConfig: item.outputConfig,
    } as TaskRequest),
    ...overrides,
  }

  function activate(
    id: string,
    queue: string[] = [],
    phase: Extract<BatchPhase, 'running' | 'paused'> = 'running',
  ): void {
    batchState = createInitialBatchState()
    deps.dispatchBatch({ type: 'started', ids: [id, ...queue] })
    deps.dispatchBatch({ type: 'queue-advanced', currentId: id, remaining: queue })
    if (phase === 'paused') {
      deps.dispatchBatch({ type: 'control-requested', kind: 'pause' })
      deps.dispatchBatch({ type: 'control-succeeded', kind: 'pause' })
    }
  }

  return { deps, items, runStates, batch: () => batchState, activate }
}

function makeItem(id: string): MediaItem {
  const preset = createTestPreset({ openOnComplete: false })
  return {
    id,
    inputPath: `/video/${id}.mp4`,
    displayName: `${id}.mp4`,
    selected: false,
    inspecting: false,
    info: null,
    decodeConfig: preset.decodeConfig,
    workflowConfig: preset.workflowConfig,
    encodeConfig: preset.encodeConfig,
    outputConfig: preset.outputConfig,
  }
}

async function runPauseTerminalRace(processedFrames: number, timeSeconds: number): Promise<BatchState> {
  const pauseCall = createDeferred()
  const harness = makeHarness({ pauseTask: vi.fn(() => pauseCall.promise) })
  harness.items.set('a', makeItem('a'))
  const runner = createBatchRunner(harness.deps)
  await runner.start(['a'])

  const pausing = runner.pause()
  await runner.onCompleted({ outputPath: '/out/a.mp4', processedFrames, timeSeconds })
  pauseCall.resolve()
  await pausing
  return harness.batch()
}

describe('batch-runner', () => {
  it('starts a queue and marks only the first item running', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a'])

    expect(harness.batch()).toMatchObject({ phase: 'running', currentId: 'a', queue: [] })
    expect(harness.runStates.get('a')?.taskState.status).toBe('running')
    expect(harness.deps.startTask).toHaveBeenCalledOnce()
  })

  it('clears a stale task issue before an accepted manual batch start', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a'])

    const setTaskIssue = vi.mocked(harness.deps.setTaskIssue)
    const checkResume = vi.mocked(harness.deps.checkResume)
    const startTask = vi.mocked(harness.deps.startTask)
    expect(setTaskIssue).toHaveBeenCalledExactlyOnceWith(null)
    expect(setTaskIssue.mock.invocationCallOrder[0])
      .toBeLessThan(checkResume.mock.invocationCallOrder[0] ?? 0)
    expect(setTaskIssue.mock.invocationCallOrder[0])
      .toBeLessThan(startTask.mock.invocationCallOrder[0] ?? 0)
    expect(harness.batch().runtimeIds).toEqual(['a'])
  })

  it('replaces the cleared issue when the accepted retry fails again', async () => {
    const retryError = new Error('CUDA retry failed')
    const harness = makeHarness({
      checkResume: vi.fn().mockRejectedValue(retryError),
    })
    harness.items.set('a', makeItem('a'))
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a'])

    expect(harness.deps.setTaskIssue).toHaveBeenNthCalledWith(1, null)
    expect(harness.deps.setTaskIssue).toHaveBeenNthCalledWith(2, {
      code: 'process_failed',
      message: 'CUDA retry failed',
      details: null,
    })
  })

  it('does nothing for an empty or already active batch', async () => {
    const harness = makeHarness()
    const runner = createBatchRunner(harness.deps)

    await runner.start([])
    harness.activate('a')
    await runner.start(['b'])

    expect(harness.batch()).toMatchObject({ phase: 'running', currentId: 'a' })
    expect(harness.deps.startTask).not.toHaveBeenCalled()
    expect(harness.deps.setTaskIssue).not.toHaveBeenCalled()
  })

  it('pauses and resumes only the batch phase, not item execution history', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    harness.activate('a')
    harness.runStates.set('a', {
      taskState: { ...createIdleTaskState(), status: 'running' },
      lastOutputPath: '',
    })
    const runner = createBatchRunner(harness.deps)

    await runner.pause()
    expect(harness.batch().phase).toBe('paused')
    expect(harness.runStates.get('a')?.taskState.status).toBe('running')

    await runner.resume()
    expect(harness.batch().phase).toBe('running')
    expect(harness.runStates.get('a')?.taskState.status).toBe('running')
  })

  it('rolls a failed pause back to its immutable snapshot', async () => {
    const harness = makeHarness({ pauseTask: vi.fn().mockRejectedValue(new Error('pause failed')) })
    harness.activate('a', ['b'])
    const runner = createBatchRunner(harness.deps)

    await runner.pause()

    expect(harness.batch()).toMatchObject({
      phase: 'running',
      currentId: 'a',
      queue: ['b'],
      controlPending: null,
    })
    expect(harness.deps.setTaskIssue).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'pause failed' }),
    )
  })

  it('allows only one control command in flight', async () => {
    const pauseCall = createDeferred()
    const harness = makeHarness({ pauseTask: vi.fn(() => pauseCall.promise) })
    harness.activate('a')
    const runner = createBatchRunner(harness.deps)

    const pausing = runner.pause()
    expect(harness.batch().controlPending).toBe('pause')
    await runner.resume()
    await runner.cancel()

    expect(harness.deps.resumeTask).not.toHaveBeenCalled()
    expect(harness.deps.cancelTask).not.toHaveBeenCalled()
    pauseCall.resolve()
    await pausing
    expect(harness.batch()).toMatchObject({ phase: 'paused', controlPending: null })
  })

  it('does not apply a stale pause result after terminal finalization', async () => {
    expect(await runPauseTerminalRace(100, 10)).toMatchObject({
      phase: 'idle',
      runtimeIds: ['a'],
    })
  })

  it('rejects stale control tokens across 100 terminal races', async () => {
    for (let iteration = 0; iteration < 100; iteration += 1) {
      expect(await runPauseTerminalRace(1, 0.1), `iteration ${iteration}`).toMatchObject({
        phase: 'idle',
        runtimeIds: ['a'],
      })
    }
  })

  it('keeps a successful cancel in cancelling until the terminal event arrives', async () => {
    const harness = makeHarness()
    harness.activate('a', ['b'], 'paused')
    const runner = createBatchRunner(harness.deps)

    await runner.cancel()

    expect(harness.batch()).toMatchObject({
      phase: 'cancelling',
      queue: [],
      currentId: 'a',
      controlPending: null,
    })
  })

  it('restores paused phase and queue after cancel failure', async () => {
    const harness = makeHarness({ cancelTask: vi.fn().mockRejectedValue(new Error('cancel failed')) })
    harness.activate('a', ['b'], 'paused')
    const runner = createBatchRunner(harness.deps)

    await runner.cancel()

    expect(harness.batch()).toMatchObject({
      phase: 'paused',
      queue: ['b'],
      currentId: 'a',
      controlPending: null,
    })
  })

  it('ignores a late cancel failure after cancellation finalized the task', async () => {
    const cancelCall = createDeferred()
    const harness = makeHarness({ cancelTask: vi.fn(() => cancelCall.promise) })
    harness.items.set('a', makeItem('a'))
    const runner = createBatchRunner(harness.deps)
    await runner.start(['a'])

    const cancelling = runner.cancel()
    await runner.onCancelled({ reason: 'user', details: null })
    cancelCall.reject(new Error('late cancellation reply'))
    await expect(cancelling).resolves.toBeUndefined()

    expect(harness.batch()).toMatchObject({ phase: 'idle', runtimeIds: ['a'] })
    expect(harness.deps.setTaskIssue).toHaveBeenLastCalledWith(null)
  })

  it('skips controls whose requested phase is already active', async () => {
    const harness = makeHarness()
    harness.activate('a', [], 'paused')
    const runner = createBatchRunner(harness.deps)

    await runner.pause()
    expect(harness.deps.pauseTask).not.toHaveBeenCalled()
    await runner.resume()
    await runner.resume()
    expect(harness.deps.resumeTask).toHaveBeenCalledOnce()
  })

  it('projects progress, log and resume metadata through special item reducers', () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    harness.activate('a')
    harness.runStates.set('a', { taskState: createIdleTaskState(), lastOutputPath: '' })
    const runner = createBatchRunner(harness.deps)

    runner.onProgress({
      current: 1,
      total: 2,
      percent: 50,
      stage: 'decode',
      stageIndex: 1,
      stageTotal: 2,
    })
    runner.onLog({ message: 'working' })
    runner.onResumeStatus({
      resumed: true,
      completedChunks: 2,
      completedOutputFrames: 40,
      startSourceFrame: 20,
      totalOutputFrames: 100,
    })

    expect(harness.runStates.get('a')?.taskState).toMatchObject({
      status: 'running',
      logs: ['working'],
      resumeStatus: { resumed: true, completedChunks: 2 },
    })
  })

  it('keeps the console item and state paired when current id is stale', () => {
    const active = makeItem('active')
    const setItemTaskState = vi.fn()
    const harness = makeHarness({
      getMediaItem: (id) => id === active.id ? active : null,
      getItemRunState: (id) => id === active.id
        ? { taskState: { ...createIdleTaskState(), logs: ['active'] }, lastOutputPath: '' }
        : null,
      getActiveItemId: () => active.id,
      setItemTaskState,
    })
    harness.activate('stale')
    const runner = createBatchRunner(harness.deps)

    runner.onLog({ message: 'working' })

    expect(setItemTaskState).toHaveBeenCalledWith(
      active.id,
      expect.objectContaining({ logs: ['active', 'working'] }),
    )
  })

  it('continues the queue and derives completion from item history', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    harness.items.set('b', makeItem('b'))
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a', 'b'])
    await runner.onCompleted({ outputPath: '/out/a.mp4', processedFrames: 100, timeSeconds: 10 })

    expect(harness.batch()).toMatchObject({ phase: 'running', currentId: 'b', queue: [] })
    expect(harness.runStates.get('a')?.taskState.status).toBe('completed')
    expect(harness.runStates.get('b')?.taskState.status).toBe('running')
  })

  it('finishes the last completed item and preserves its history', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a'])
    await runner.onCompleted({ outputPath: '/out/a.mp4', processedFrames: 100, timeSeconds: 10 })

    expect(harness.batch()).toMatchObject({ phase: 'idle', runtimeIds: ['a'] })
    expect(harness.runStates.get('a')?.taskState.status).toBe('completed')
  })

  it('replaces the completed runtime ids only when the next valid batch starts', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    harness.items.set('b', makeItem('b'))
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a'])
    await runner.onCompleted({ outputPath: '/out/a.mp4', processedFrames: 100, timeSeconds: 10 })
    expect(harness.batch()).toMatchObject({ phase: 'idle', runtimeIds: ['a'] })

    await runner.start(['b'])
    expect(harness.batch()).toMatchObject({ phase: 'running', runtimeIds: ['b'] })
  })

  it('records errors and continues with the next item', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    harness.items.set('b', makeItem('b'))
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a', 'b'])
    const error = { code: 'process_failed' as const, message: 'fail', details: null }
    await runner.onError(error)

    expect(harness.runStates.get('a')?.taskState.status).toBe('error')
    expect(harness.batch().currentId).toBe('b')
    expect(harness.deps.setTaskIssue).toHaveBeenNthCalledWith(1, null)
    expect(harness.deps.setTaskIssue).toHaveBeenNthCalledWith(2, error)
    expect(harness.deps.setTaskIssue).toHaveBeenCalledTimes(2)
  })

  it('preserves the typed missing-model error for the global task banner', async () => {
    const harness = makeHarness()
    harness.items.set('a', makeItem('a'))
    const runner = createBatchRunner(harness.deps)
    await runner.start(['a'])
    const error = {
      code: 'missing_model' as const,
      message: 'Real-RawVSR BasicVSR x3 model weight is missing',
      details: { algorithm: 'real-rawvsr-basicvsr', scale_factor: 3 },
    }

    await runner.onError(error)

    expect(harness.deps.setTaskIssue).toHaveBeenCalledWith(error)
    expect(harness.runStates.get('a')?.taskState.status).toBe('error')
  })

  it('keeps user cancellation silent and surfaces watchdog stalls', async () => {
    const userHarness = makeHarness()
    userHarness.items.set('a', makeItem('a'))
    const userRunner = createBatchRunner(userHarness.deps)
    await userRunner.start(['a'])
    await userRunner.onCancelled({ reason: 'user', details: null })
    expect(userHarness.deps.setTaskIssue).toHaveBeenLastCalledWith(null)

    const stalledHarness = makeHarness()
    stalledHarness.items.set('a', makeItem('a'))
    const stalledRunner = createBatchRunner(stalledHarness.deps)
    await stalledRunner.start(['a'])
    await stalledRunner.onCancelled({ reason: 'stalled', details: { stderr: 'hung' } })
    expect(stalledHarness.deps.setTaskIssue).toHaveBeenCalledWith(
      expect.objectContaining({ code: 'process_failed', details: { stderr: 'hung' } }),
    )
  })

  it('stashes and resumes a detected output conflict', async () => {
    const item = makeItem('a')
    const buildRequest = vi.fn((mediaItem: MediaItem, resumeMode?: TaskRequest['resumeMode']) => ({
      inputPath: mediaItem.inputPath,
      decodeConfig: mediaItem.decodeConfig,
      workflowConfig: mediaItem.workflowConfig,
      encodeConfig: mediaItem.encodeConfig,
      outputConfig: mediaItem.outputConfig,
      resumeMode,
    } as TaskRequest))
    const harness = makeHarness({
      checkResume: vi.fn().mockResolvedValue({
        type: 'resume_inspection',
        pipeline_kind: 'streaming',
        outputPath: '/out/a.mp4',
        input_path: '/video/a.mp4',
        finalExists: true,
        sidecarExists: true,
        signatureMatch: true,
        completedChunks: 3,
        completedOutputFrames: 90,
        nextSourceFrame: 0,
        totalOutputFrames: 100,
      }),
      buildRequest,
    })
    harness.items.set('a', item)
    const runner = createBatchRunner(harness.deps)

    await runner.start(['a'])
    expect(harness.deps.startTask).not.toHaveBeenCalled()
    expect(harness.deps.setPendingConflict).toHaveBeenCalled()

    await runner.resolveConflict('resume')
    expect(buildRequest).toHaveBeenLastCalledWith(item, 'force-resume')
    expect(harness.deps.startTask).toHaveBeenCalledWith(
      expect.objectContaining({ resumeMode: 'force-resume' }),
    )
  })
})
