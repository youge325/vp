import { describe, expect, it, vi } from 'vitest'
import { createBatchRunner } from '@/services/task/batch-runner'
import type { BatchState } from '@/types/domain/batch'
import type { MediaItem, MediaRunState, MediaTaskState } from '@/types/domain/media'
import { createIdleTaskState } from '@/services/task/events'
import type { TaskRequest } from '@/types/protocol'
import { createDeferred } from '../../fixtures/deferred'
import { createTestPreset } from '../../fixtures/preset'

type BatchRunnerDeps = Parameters<typeof createBatchRunner>[0]

function makeDeps(overrides: Partial<BatchRunnerDeps> = {}): BatchRunnerDeps {
  const batchState: BatchState = {
    queue: [],
    currentId: null,
    completedCount: 0,
    isRunning: false,
    isPaused: false,
    isCancelling: false,
    controlPending: null,
  }
  const runtimeIds: string[] = []
  const items = new Map<string, MediaItem>()
  const runStates = new Map<string, MediaRunState>()

  return {
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
    setItemLastOutputPath: vi.fn(),
    resetItemRunState: vi.fn(),
    setActiveItem: vi.fn(),
    getActiveItemId: () => null,

    getBatch: () => batchState,
    setBatch: (partial) => { Object.assign(batchState, partial) },
    getRuntimeIds: () => runtimeIds,
    setRuntimeIds: (ids) => { runtimeIds.length = 0; runtimeIds.push(...ids) },
    setPendingConflict: vi.fn(),

    buildRequest: (item) => ({ inputPath: item.inputPath, decodeConfig: item.decodeConfig, workflowConfig: item.workflowConfig, encodeConfig: item.encodeConfig, outputConfig: item.outputConfig } as TaskRequest),

    ...overrides,
  }
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

describe('batch-runner', () => {
  it('starts a batch and sets the first item to running', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const item = makeItem('a')
    deps.getMediaItem = () => item

    await runner.start(['a'])

    expect(deps.getBatch().isRunning).toBe(true)
    expect(deps.getBatch().currentId).toBe('a')
    expect(deps.startTask).toHaveBeenCalledOnce()
  })

  it('does nothing when starting an empty batch', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    await runner.start([])
    expect(deps.getBatch().isRunning).toBe(false)
  })

  it('pauses the current task', async () => {
    const setItemTaskState = vi.fn()
    const deps = makeDeps({
      getItemRunState: () => ({ taskState: createIdleTaskState(), lastOutputPath: '' }),
      setItemTaskState,
    })
    const runner = createBatchRunner(deps)
    const item = makeItem('a')
    deps.getMediaItem = () => item
    deps.getBatch().isRunning = true
    deps.getBatch().currentId = 'a'

    await runner.pause()
    expect(deps.pauseTask).toHaveBeenCalledOnce()
    expect(deps.getBatch().isPaused).toBe(true)
    expect(setItemTaskState).toHaveBeenCalledWith(
      'a',
      expect.objectContaining({ status: 'paused' }),
    )
  })

  it('resumes the current task through the shared pause-state transition', async () => {
    const setItemTaskState = vi.fn()
    const deps = makeDeps({
      getItemRunState: () => ({
        taskState: { ...createIdleTaskState(), status: 'paused' },
        lastOutputPath: '',
      }),
      setItemTaskState,
    })
    const runner = createBatchRunner(deps)
    const item = makeItem('a')
    deps.getMediaItem = () => item
    deps.getBatch().isRunning = true
    deps.getBatch().isPaused = true
    deps.getBatch().currentId = 'a'

    await runner.resume()

    expect(deps.resumeTask).toHaveBeenCalledOnce()
    expect(deps.getBatch().isPaused).toBe(false)
    expect(setItemTaskState).toHaveBeenCalledWith(
      'a',
      expect.objectContaining({ status: 'running' }),
    )
  })

  it('reports a pause command failure through the task issue port', async () => {
    const deps = makeDeps({ pauseTask: vi.fn().mockRejectedValue(new Error('pause failed')) })
    const runner = createBatchRunner(deps)
    deps.getBatch().isRunning = true

    await expect(runner.pause()).resolves.toBeUndefined()

    expect(deps.getBatch().isPaused).toBe(false)
    expect(deps.getBatch().controlPending).toBeNull()
    expect(deps.setTaskIssue).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'pause failed' }),
    )
  })

  it('allows only one control command in flight', async () => {
    const pauseCall = createDeferred()
    const deps = makeDeps({
      pauseTask: vi.fn(() => pauseCall.promise),
    })
    const runner = createBatchRunner(deps)
    deps.getBatch().isRunning = true

    const pausing = runner.pause()
    expect(deps.getBatch().controlPending).toBe('pause')

    await runner.resume()
    await runner.cancel()

    expect(deps.resumeTask).not.toHaveBeenCalled()
    expect(deps.cancelTask).not.toHaveBeenCalled()

    pauseCall.resolve()
    await pausing

    expect(deps.getBatch().isPaused).toBe(true)
    expect(deps.getBatch().controlPending).toBeNull()
  })

  it('does not apply a stale pause result after the task reaches a terminal state', async () => {
    const pauseCall = createDeferred()
    const deps = makeDeps({
      pauseTask: vi.fn(() => pauseCall.promise),
    })
    const item = makeItem('a')
    deps.getMediaItem = () => item
    const runner = createBatchRunner(deps)

    await runner.start(['a'])
    const pausing = runner.pause()
    await runner.onCompleted({
      outputPath: '/out/a.mp4',
      processedFrames: 100,
      timeSeconds: 10,
    })

    pauseCall.resolve()
    await pausing

    expect(deps.getBatch()).toMatchObject({
      isRunning: false,
      isPaused: false,
      controlPending: null,
    })
  })

  it('ignores a late cancel failure after a cancellation event finalized the task', async () => {
    const cancelCall = createDeferred()
    const deps = makeDeps({
      cancelTask: vi.fn(() => cancelCall.promise),
    })
    const item = makeItem('a')
    deps.getMediaItem = () => item
    const runner = createBatchRunner(deps)

    await runner.start(['a'])
    const cancelling = runner.cancel()
    expect(deps.getBatch()).toMatchObject({
      isCancelling: true,
      controlPending: 'cancel',
    })

    await runner.onCancelled({ reason: 'user', details: null })
    cancelCall.reject(new Error('late cancellation reply'))
    await expect(cancelling).resolves.toBeUndefined()

    expect(deps.getBatch()).toMatchObject({
      isRunning: false,
      isCancelling: false,
      controlPending: null,
    })
    expect(deps.setTaskIssue).toHaveBeenLastCalledWith(null)
  })

  it('reports cancel failures and rolls back the optimistic cancelling state', async () => {
    const deps = makeDeps({
      cancelTask: vi.fn().mockRejectedValue(new Error('cancel failed')),
    })
    const item = makeItem('a')
    deps.getMediaItem = () => item
    const runner = createBatchRunner(deps)

    await runner.start(['a'])
    await expect(runner.cancel()).resolves.toBeUndefined()

    expect(deps.getBatch()).toMatchObject({
      isRunning: true,
      isCancelling: false,
      controlPending: null,
    })
    expect(deps.setTaskIssue).toHaveBeenCalledWith(
      expect.objectContaining({ message: 'cancel failed' }),
    )
  })

  it('skips pause and resume commands when the requested state is already active', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    deps.getBatch().isRunning = true
    deps.getBatch().isPaused = true

    await runner.pause()
    expect(deps.pauseTask).not.toHaveBeenCalled()

    deps.getBatch().isPaused = false
    await runner.resume()
    expect(deps.resumeTask).not.toHaveBeenCalled()
  })

  it('projects progress, log and resume events through the console task state', () => {
    const item = makeItem('a')
    let runState: MediaRunState = {
      taskState: createIdleTaskState(),
      lastOutputPath: '',
    }
    const setItemTaskState = vi.fn((_id: string, taskState: MediaTaskState) => {
      runState = { ...runState, taskState }
    })
    const deps = makeDeps({
      getMediaItem: () => item,
      getItemRunState: () => runState,
      setItemTaskState,
    })
    deps.getBatch().currentId = 'a'
    const runner = createBatchRunner(deps)

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

    expect(runState.taskState.status).toBe('running')
    expect(runState.taskState.logs).toEqual(['working'])
    expect(runState.taskState.resumeStatus).toEqual({
      resumed: true,
      completedChunks: 2,
      completedOutputFrames: 40,
      startSourceFrame: 20,
      totalOutputFrames: 100,
    })
    expect(setItemTaskState).toHaveBeenCalledTimes(3)
  })

  it('keeps the console item and run state paired when a stale current id falls back to the active item', () => {
    const activeItem = makeItem('active')
    const staleState: MediaRunState = {
      taskState: { ...createIdleTaskState(), logs: ['stale'] },
      lastOutputPath: '',
    }
    const activeState: MediaRunState = {
      taskState: { ...createIdleTaskState(), logs: ['active'] },
      lastOutputPath: '',
    }
    const setItemTaskState = vi.fn()
    const deps = makeDeps({
      getMediaItem: (id) => id === activeItem.id ? activeItem : null,
      getItemRunState: (id) => id === 'stale' ? staleState : id === activeItem.id ? activeState : null,
      getActiveItemId: () => activeItem.id,
      setItemTaskState,
    })
    deps.getBatch().currentId = 'stale'
    const runner = createBatchRunner(deps)

    runner.onLog({ message: 'working' })

    expect(setItemTaskState).toHaveBeenCalledWith(
      activeItem.id,
      expect.objectContaining({ logs: ['active', 'working'] }),
    )
  })

  it('cancels the batch', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const item = makeItem('a')
    deps.getMediaItem = () => item
    deps.getBatch().isRunning = true
    deps.getBatch().currentId = 'a'

    await runner.cancel()
    expect(deps.cancelTask).toHaveBeenCalledOnce()
    expect(deps.getBatch().isCancelling).toBe(true)
  })

  it('handles completed event and finalizes', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const itemA = makeItem('a')
    const itemB = makeItem('b')
    deps.getMediaItem = (id) => id === 'a' ? itemA : id === 'b' ? itemB : null

    await runner.start(['a', 'b'])
    // Complete the first item; counters are reset only when the entire batch finishes.
    await runner.onCompleted({ outputPath: '/out/a.mp4', processedFrames: 100, timeSeconds: 10 })

    expect(deps.getBatch().isRunning).toBe(true)
    expect(deps.getBatch().completedCount).toBe(1)
  })

  it('retains the completed projection after the real finalization path', async () => {
    const deps = makeDeps()
    const item = makeItem('a')
    deps.getMediaItem = () => item
    const runner = createBatchRunner(deps)

    await runner.start(['a'])
    await runner.onCompleted({ outputPath: '/out/a.mp4', processedFrames: 100, timeSeconds: 10 })

    expect(deps.getBatch()).toMatchObject({
      currentId: null,
      completedCount: 1,
      isRunning: false,
    })
    expect(deps.getRuntimeIds()).toEqual(['a'])
    expect(deps.getItemRunState('a')?.taskState.status).toBe('completed')

    await runner.start(['a'])

    expect(deps.getBatch()).toMatchObject({
      completedCount: 0,
      isRunning: true,
    })
    expect(deps.getItemRunState('a')?.taskState.status).toBe('running')
  })

  it('handles error event and finalizes', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const itemA = makeItem('a')
    const itemB = makeItem('b')
    deps.getMediaItem = (id) => id === 'a' ? itemA : id === 'b' ? itemB : null

    await runner.start(['a', 'b'])
    await runner.onError({ code: 'process_failed', message: 'fail', details: null })

    expect(deps.getBatch().isRunning).toBe(true)
    expect(deps.getBatch().currentId).toBe('b')
  })

  it('routes onError to setTaskIssue so the task banner picks it up', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const itemA = makeItem('a')
    deps.getMediaItem = (id) => id === 'a' ? itemA : null

    await runner.start(['a'])
    const err = { code: 'process_failed' as const, message: 'boom', details: null }
    await runner.onError(err)

    expect(deps.setTaskIssue).toHaveBeenCalledWith(err)
  })

  it('user-initiated cancel clears the task banner instead of surfacing it', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const itemA = makeItem('a')
    deps.getMediaItem = (id) => id === 'a' ? itemA : null

    await runner.start(['a'])
    await runner.onCancelled({ reason: 'user', details: null })

    expect(deps.setTaskIssue).toHaveBeenLastCalledWith(null)
  })

  it('stalled cancel surfaces a ProcessFailed banner via setTaskIssue', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const itemA = makeItem('a')
    deps.getMediaItem = (id) => id === 'a' ? itemA : null

    await runner.start(['a'])
    await runner.onCancelled({ reason: 'stalled', details: { stderr: 'hung' } })

    // 取出 setTaskIssue 最后一次调用的实参,验证形状
    const calls = (deps.setTaskIssue as ReturnType<typeof vi.fn>).mock.calls
    const lastArg = calls[calls.length - 1]?.[0] as { code: string; details: unknown } | null
    expect(lastArg).not.toBeNull()
    expect(lastArg?.code).toBe('process_failed')
    expect(lastArg?.details).toEqual({ stderr: 'hung' })
  })

  it('sets pending conflict when resume conflict detected', async () => {
    const deps = makeDeps()
    deps.checkResume = vi.fn().mockResolvedValue({
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
    })
    const runner = createBatchRunner(deps)
    const item = makeItem('a')
    deps.getMediaItem = () => item

    await runner.start(['a'])

    expect(deps.getBatch().currentId).toBe('a')
    expect(deps.startTask).not.toHaveBeenCalled()
  })

  it('relaunches an accepted resume conflict with force-resume', async () => {
    const item = makeItem('a')
    const buildRequest = vi.fn((mediaItem: MediaItem, resumeMode?: TaskRequest['resumeMode']) => ({
      inputPath: mediaItem.inputPath,
      decodeConfig: mediaItem.decodeConfig,
      workflowConfig: mediaItem.workflowConfig,
      encodeConfig: mediaItem.encodeConfig,
      outputConfig: mediaItem.outputConfig,
      resumeMode,
    } as TaskRequest))
    const deps = makeDeps({
      getMediaItem: () => item,
      buildRequest,
    })
    deps.getBatch().currentId = item.id
    deps.getBatch().isRunning = true
    const runner = createBatchRunner(deps)

    await runner.resolveConflict('resume')

    expect(buildRequest).toHaveBeenCalledWith(item, 'force-resume')
    expect(deps.startTask).toHaveBeenCalledWith(
      expect.objectContaining({ resumeMode: 'force-resume' }),
    )
  })
})
