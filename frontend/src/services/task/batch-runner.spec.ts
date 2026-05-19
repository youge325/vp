import { describe, expect, it, vi } from 'vitest'
import { createBatchRunner, type BatchRunnerDeps } from './batch-runner'
import type { BatchState, ResumeConflictDescriptor } from '@/types/domain/batch'
import type { MediaItem, MediaRunState, MediaTaskState } from '@/types/domain/media'
import { createIdleTaskState } from './events'
import type { TaskRequest } from '@/types/protocol'

function makeDeps(overrides: Partial<BatchRunnerDeps> = {}): BatchRunnerDeps {
  const batchState: BatchState = {
    queue: [],
    currentId: null,
    completedCount: 0,
    failedCount: 0,
    isRunning: false,
    isPaused: false,
    isCancelling: false,
  }
  const runtimeIds: string[] = []
  let pendingConflict: ResumeConflictDescriptor | null = null
  const items = new Map<string, MediaItem>()
  // Phase 13.1 — run state lives in its own store; fake here keeps the
  // same Map shape so test cases can probe what's been written to it.
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
      inputPath: '',
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
      const existing = runStates.get(id) ?? { taskState: createIdleTaskState(), issue: null, lastOutputPath: '' }
      runStates.set(id, { ...existing, taskState: state })
    },
    setItemIssue: vi.fn(),
    setItemLastOutputPath: vi.fn(),
    resetItemRunState: vi.fn(),
    resetItemsRunState: vi.fn(),
    setActiveItem: vi.fn(),
    getActiveItemId: () => null,

    getBatch: () => batchState,
    setBatch: (partial) => { Object.assign(batchState, partial) },
    getRuntimeIds: () => runtimeIds,
    setRuntimeIds: (ids) => { runtimeIds.length = 0; runtimeIds.push(...ids) },
    setPendingConflict: (d) => { pendingConflict = d },

    buildRequest: (item) => ({ inputPath: item.inputPath, decodeConfig: item.decodeConfig, workflowConfig: item.workflowConfig, encodeConfig: item.encodeConfig, outputConfig: item.outputConfig } as TaskRequest),

    ...overrides,
  }
}

function makeItem(id: string): MediaItem {
  return {
    id,
    inputPath: `/video/${id}.mp4`,
    displayName: `${id}.mp4`,
    selected: false,
    inspecting: false,
    info: null,
    decodeConfig: { mode: 'software', hwaccel: '', hwaccelDevice: '', decoder: 'software', options: {} },
    workflowConfig: { fpsMode: 'target', processOrder: 'super_resolution_then_interpolation', interpolation: { enabled: false, targetFps: 60, multi: 2, model: '4.25', onnxModel: '', scale: 1, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' }, superResolution: { enabled: false, scaleFactor: 2, algorithm: 'placeholder', onnxModel: '' }, anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 }, preprocess: { enabled: false, filters: [] }, postprocess: { enabled: false, filters: [] } },
    encodeConfig: { codec: 'libx265', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
    outputConfig: { outputDir: '', openOnComplete: false, segmentFrames: 1000 },
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
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const item = makeItem('a')
    deps.getMediaItem = () => item
    deps.getBatch().isRunning = true
    deps.getBatch().currentId = 'a'

    await runner.pause()
    expect(deps.pauseTask).toHaveBeenCalledOnce()
    expect(deps.getBatch().isPaused).toBe(true)
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

  it('handles error event and finalizes', async () => {
    const deps = makeDeps()
    const runner = createBatchRunner(deps)
    const itemA = makeItem('a')
    const itemB = makeItem('b')
    deps.getMediaItem = (id) => id === 'a' ? itemA : id === 'b' ? itemB : null

    await runner.start(['a', 'b'])
    await runner.onError({ code: 'test_error', message: 'fail', details: null })

    expect(deps.getBatch().isRunning).toBe(true)
    expect(deps.getBatch().failedCount).toBe(1)
  })

  it('sets pending conflict when resume conflict detected', async () => {
    const deps = makeDeps()
    deps.checkResume = vi.fn().mockResolvedValue({
      type: 'resume_inspection',
      pipeline_kind: 'streaming',
      outputPath: '/out/a.mp4',
      inputPath: '/video/a.mp4',
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
})
