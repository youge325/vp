import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useWorkbenchStore } from '@/stores/workbench'
import type { EnvironmentCheckPayload, EnvironmentCheckResult, VideoInfoResult, WorkbenchPreset } from '@/types'

interface TaskEventHandlers {
  onProgress: (payload: Record<string, unknown>) => void
  onLog: (payload: Record<string, unknown>) => void
  onCompleted: (payload: Record<string, unknown>) => void
  onError: (payload: { code: string; message: string; details?: Record<string, unknown> | null }) => void
  onCancelled: () => void
}

const handlersRef: { current: TaskEventHandlers | null } = { current: null }

const mockCheckEnvironment = vi.fn<(forceRefresh?: boolean) => Promise<EnvironmentCheckPayload>>()
const mockInspectVideo = vi.fn<(inputPath: string) => Promise<VideoInfoResult>>()
const mockStartTask = vi.fn<(request: unknown) => Promise<void>>()
const mockCancelTask = vi.fn<() => Promise<void>>()
const mockPickInputs = vi.fn<() => Promise<string[]>>()
const mockPickOutputDirectory = vi.fn<() => Promise<string | null>>()
const mockOpenOutputLocation = vi.fn<(path: string) => Promise<void>>()
const mockLoadWorkbenchPreset = vi.fn<() => Promise<WorkbenchPreset | null>>()
const mockSaveWorkbenchPreset = vi.fn<(preset: WorkbenchPreset) => Promise<void>>()

vi.mock('@/lib/tauri', () => ({
  cancelTask: () => mockCancelTask(),
  checkEnvironment: (forceRefresh?: boolean) => mockCheckEnvironment(forceRefresh),
  inspectVideo: (inputPath: string) => mockInspectVideo(inputPath),
  listenTaskEvents: async (handlers: TaskEventHandlers) => {
    handlersRef.current = handlers
    return () => {
      handlersRef.current = null
    }
  },
  loadWorkbenchPreset: () => mockLoadWorkbenchPreset(),
  openOutputLocation: (path: string) => mockOpenOutputLocation(path),
  pickInputs: () => mockPickInputs(),
  pickOutputDirectory: () => mockPickOutputDirectory(),
  saveWorkbenchPreset: (preset: WorkbenchPreset) => mockSaveWorkbenchPreset(preset),
  startTask: (request: unknown) => mockStartTask(request),
}))

function makeEnvResult(): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      available: true,
      version: 'ffmpeg n7',
      path: 'D:/ffmpeg/bin/ffmpeg.exe',
      ffprobe_path: 'D:/ffmpeg/bin/ffprobe.exe',
      hwaccels: ['cuda', 'qsv'],
      encoderProfiles: [
        {
          name: 'hevc_nvenc',
          label: 'NVENC H.265',
          family: 'nvidia',
          codec: 'hevc',
          available: true,
          pixelFormats: ['p010le'],
          hardwareDevices: ['cuda'],
          options: [],
        },
      ],
      decoderProfiles: [
        {
          name: 'software',
          label: 'Software Decode',
          family: 'software',
          codec: 'any',
          available: true,
          pixelFormats: [],
          hardwareDevices: [],
          options: [],
        },
        {
          name: 'hevc_cuvid',
          label: 'NVDEC H.265',
          family: 'nvidia',
          codec: 'hevc',
          available: true,
          pixelFormats: [],
          hardwareDevices: ['cuda'],
          options: [],
        },
        {
          name: 'h264_cuvid',
          label: 'NVDEC H.264',
          family: 'nvidia',
          codec: 'h264',
          available: true,
          pixelFormats: [],
          hardwareDevices: ['cuda'],
          options: [],
        },
      ],
    },
    gpu: {
      available: true,
      devices: ['NVIDIA GeForce RTX 3070'],
      adapters: [
        {
          name: 'NVIDIA GeForce RTX 3070',
          vendor: 'nvidia',
          device_type: 'discrete',
          adapter_compatibility: 'NVIDIA',
          driver_version: '1',
        } as unknown as never,
      ],
      cuda_available: true,
    },
    tensor_backends: {
      pytorch: true,
      paddle: false,
    },
    rife_model: {
      available: true,
      version: '4.25',
      path: 'D:/model',
    },
    runtime: {
      mode: 'desktop',
      bundled: false,
      python_executable: 'python',
      default_model_available: true,
    },
    resources: {},
  }
}

function makeEnvPayload(
  source: EnvironmentCheckPayload['source'] = 'probe',
  checkedAt = '2026-04-23T11:00:00Z',
): EnvironmentCheckPayload {
  return {
    result: makeEnvResult(),
    source,
    checkedAt,
  }
}

function makeVideoInfo(inputPath: string, videoCodec = 'hevc'): VideoInfoResult {
  return {
    type: 'info',
    fps: 24,
    frames: 240,
    duration: 10,
    width: inputPath.includes('4k') ? 3840 : 1920,
    height: inputPath.includes('4k') ? 2160 : 1080,
    has_audio: true,
    video_codec: videoCodec,
  }
}

function makePreset(): WorkbenchPreset {
  return {
    decodeConfig: {
      mode: 'hardware',
      hwaccel: 'cuda',
      hwaccelDevice: '0',
      decoder: 'hevc_cuvid',
      options: {},
    },
    workflowConfig: {
      fpsMode: 'target',
      processOrder: 'super_resolution_then_interpolation',
      interpolation: {
        enabled: false,
        targetFps: 48,
        multi: 2,
        model: '4.25',
        scale: 1,
        fp16: false,
        tensorBackend: 'pytorch',
      },
      superResolution: {
        enabled: false,
        scaleFactor: 2,
        algorithm: 'placeholder',
      },
      anime: {
        enabled: true,
        profile: 'clean-lines',
        denoise: 12,
        edgeBoost: 16,
      },
    },
    encodeConfig: {
      codec: 'hevc_nvenc',
      family: 'nvidia',
      container: 'mkv',
      keepAudio: false,
      rateControl: {
        mode: 'cq',
        value: 20,
      },
      options: {},
    },
    outputConfig: {
      outputDir: 'D:/output/preset',
      openOnComplete: false,
      segmentFrames: 240,
    },
  }
}

async function flush(): Promise<void> {
  await Promise.resolve()
  await Promise.resolve()
}

describe('workbench store', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    handlersRef.current = null
    mockCheckEnvironment.mockReset()
    mockInspectVideo.mockReset()
    mockStartTask.mockReset()
    mockCancelTask.mockReset()
    mockPickInputs.mockReset()
    mockPickOutputDirectory.mockReset()
    mockOpenOutputLocation.mockReset()
    mockLoadWorkbenchPreset.mockReset()
    mockSaveWorkbenchPreset.mockReset()

    mockCheckEnvironment.mockResolvedValue(makeEnvPayload())
    mockInspectVideo.mockImplementation(async (inputPath: string) =>
      makeVideoInfo(inputPath, inputPath.includes('h264') ? 'h264' : 'hevc'),
    )
    mockStartTask.mockResolvedValue()
    mockCancelTask.mockResolvedValue()
    mockPickInputs.mockResolvedValue([])
    mockPickOutputDirectory.mockResolvedValue(null)
    mockOpenOutputLocation.mockResolvedValue()
    mockLoadWorkbenchPreset.mockResolvedValue(null)
    mockSaveWorkbenchPreset.mockResolvedValue()
  })

  afterEach(async () => {
    await vi.runOnlyPendingTimersAsync()
    vi.useRealTimers()
  })

  it('bootstraps environment probing on startup', async () => {
    const store = useWorkbenchStore()

    await store.bootstrap()

    expect(mockLoadWorkbenchPreset).toHaveBeenCalledTimes(1)
    expect(mockCheckEnvironment).toHaveBeenCalledTimes(1)
    expect(mockCheckEnvironment).toHaveBeenCalledWith(false)
    expect(store.env.checkResult?.ffmpeg.available).toBe(true)
    expect(store.env.checkResult?.gpu.adapters[0]?.deviceType).toBe('discrete')
    expect(store.env.checkSource).toBe('probe')
    expect(store.env.lastProbeAt).toBe('2026-04-23T11:00:00Z')
    expect(store.editingScope).toBe('preset')
  })

  it('exposes editable draft presets before any media is imported', async () => {
    const store = useWorkbenchStore()

    await store.bootstrap()

    expect(store.activeItem).toBeNull()
    expect(store.editingScope).toBe('preset')
    expect(store.editor.decodeConfig.mode).toBe('hardware')
    expect(store.editor.decodeConfig.decoder).toBe('hevc_cuvid')
    expect(store.editor.workflowConfig.interpolation.enabled).toBe(true)
    expect(store.visibleDecoderProfiles).toHaveLength(3)
  })

  it('imports files without polluting env issues', async () => {
    const store = useWorkbenchStore()
    await store.bootstrap()
    mockPickInputs.mockResolvedValueOnce(['D:/input/a.mp4'])

    await store.pickInputs()

    expect(store.mediaItems).toHaveLength(1)
    expect(store.env.issue).toBeNull()
    expect(store.operationIssue).toBeNull()
  })

  it('stores pickInputs failures as input operation issues', async () => {
    const store = useWorkbenchStore()
    await store.bootstrap()
    mockPickInputs.mockRejectedValueOnce(new Error('pick_inputs not allowed'))

    await store.pickInputs()

    expect(store.env.issue).toBeNull()
    expect(store.operationIssue?.scope).toBe('input')
    expect(store.operationIssue?.error.code).toBe('pick_inputs_failed')
    expect(store.operationIssue?.error.message).toContain('pick_inputs')
  })

  it('keeps environment failures in env.issue', async () => {
    const store = useWorkbenchStore()
    mockCheckEnvironment.mockRejectedValueOnce(new Error('ffmpeg missing'))

    await store.recheckEnvironment()

    expect(mockCheckEnvironment).toHaveBeenCalledWith(true)
    expect(store.env.issue?.code).toBe('check_failed')
    expect(store.operationIssue).toBeNull()
  })

  it('updates the draft preset and selected items together when workflow settings change', async () => {
    const store = useWorkbenchStore()
    await store.bootstrap()
    await store.addMediaPaths(['D:/input/a.mp4', 'D:/input/b.mp4', 'D:/input/c.mp4'])

    const [first, second, third] = store.mediaItems
    store.setActiveItem(first.id)
    store.setItemSelected(first.id, true)
    store.setItemSelected(second.id, true)
    store.setItemSelected(third.id, false)

    store.patchWorkflow((config) => {
      config.interpolation.enabled = false
      config.anime.enabled = true
    })

    expect(store.draftPreset.workflowConfig.interpolation.enabled).toBe(false)
    expect(store.draftPreset.workflowConfig.anime.enabled).toBe(true)
    expect(first.workflowConfig.interpolation.enabled).toBe(false)
    expect(second.workflowConfig.interpolation.enabled).toBe(false)
    expect(third.workflowConfig.interpolation.enabled).toBe(true)
    expect(first.workflowConfig.anime.enabled).toBe(true)
    expect(second.workflowConfig.anime.enabled).toBe(true)
    expect(third.workflowConfig.anime.enabled).toBe(false)
  })

  it('imports new media with the persisted preset defaults', async () => {
    const store = useWorkbenchStore()
    mockLoadWorkbenchPreset.mockResolvedValueOnce(makePreset())

    await store.bootstrap()
    await store.addMediaPaths(['D:/input/a.mp4'])

    expect(store.mediaItems).toHaveLength(1)
    expect(store.draftPreset.outputConfig.outputDir).toBe('D:/output/preset')
    expect(store.draftPreset.workflowConfig.interpolation.enabled).toBe(false)
    expect(store.mediaItems[0]?.decodeConfig.hwaccelDevice).toBe('0')
    expect(store.mediaItems[0]?.workflowConfig.anime.enabled).toBe(true)
    expect(store.mediaItems[0]?.encodeConfig.container).toBe('mkv')
    expect(store.mediaItems[0]?.outputConfig.outputDir).toBe('D:/output/preset')
  })

  it('remaps persisted decoders to the same hardware family when the imported codec changes', async () => {
    const store = useWorkbenchStore()
    mockLoadWorkbenchPreset.mockResolvedValueOnce(makePreset())

    await store.bootstrap()
    await store.addMediaPaths(['D:/input/h264-demo.mp4'])

    expect(store.mediaItems[0]?.info?.video_codec).toBe('h264')
    expect(store.mediaItems[0]?.decodeConfig.mode).toBe('hardware')
    expect(store.mediaItems[0]?.decodeConfig.hwaccel).toBe('cuda')
    expect(store.mediaItems[0]?.decodeConfig.hwaccelDevice).toBe('0')
    expect(store.mediaItems[0]?.decodeConfig.decoder).toBe('h264_cuvid')
  })

  it('forces a fresh environment probe when rechecking manually', async () => {
    const store = useWorkbenchStore()

    await store.bootstrap()
    await store.recheckEnvironment()

    expect(mockCheckEnvironment).toHaveBeenNthCalledWith(1, false)
    expect(mockCheckEnvironment).toHaveBeenNthCalledWith(2, true)
  })

  it('persists preset edits with debounce while no media is selected', async () => {
    const store = useWorkbenchStore()

    await store.bootstrap()
    mockSaveWorkbenchPreset.mockClear()

    store.patchOutput((config) => {
      config.outputDir = 'D:/output/debounced'
    })

    expect(mockSaveWorkbenchPreset).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(300)

    expect(mockSaveWorkbenchPreset).toHaveBeenCalledTimes(1)
    expect(mockSaveWorkbenchPreset.mock.calls[0]?.[0].outputConfig.outputDir).toBe('D:/output/debounced')
  })

  it('advances the batch queue and clears runtime artifacts after the batch finishes', async () => {
    const store = useWorkbenchStore()
    await store.bootstrap()
    await store.addMediaPaths(['D:/input/a.mp4', 'D:/input/b.mp4', 'D:/input/c.mp4'])
    await store.attachTaskListeners()

    expect(handlersRef.current).not.toBeNull()

    await store.startBatch()
    expect(store.currentTaskItem?.displayName).toBe('a.mp4')
    expect(mockStartTask).toHaveBeenCalledTimes(1)

    handlersRef.current?.onCompleted({
      outputPath: 'D:/output/a_processed.mp4',
      processedFrames: 240,
      timeSeconds: 12,
    })
    await flush()

    expect(store.batch.completedCount).toBe(1)
    expect(store.currentTaskItem?.displayName).toBe('b.mp4')

    handlersRef.current?.onError({
      code: 'process_failed',
      message: 'boom',
      details: null,
    })
    await flush()

    expect(store.batch.failedCount).toBe(1)
    expect(store.currentTaskItem?.displayName).toBe('c.mp4')

    handlersRef.current?.onCancelled()
    await flush()

    expect(store.batch.completedCount).toBe(0)
    expect(store.batch.failedCount).toBe(0)
    expect(store.batch.isRunning).toBe(false)
    expect(store.currentTaskItem).toBeNull()
    expect(store.mediaItems.every((item) => item.taskState.status === 'idle')).toBe(true)
    expect(store.mediaItems.every((item) => item.lastOutputPath === '')).toBe(true)
    expect(store.mediaItems.every((item) => item.issue === null)).toBe(true)
  })

  it('opens the configured output directory without falling back to the last completed result', async () => {
    const store = useWorkbenchStore()
    await store.bootstrap()
    await store.addMediaPaths(['D:/input/a.mp4'])
    await store.attachTaskListeners()

    store.patchOutput((config) => {
      config.outputDir = 'D:/output/final'
      config.openOnComplete = false
    })

    await store.startBatch()
    handlersRef.current?.onCompleted({
      outputPath: 'D:/output/final/a_processed.mp4',
      processedFrames: 240,
      timeSeconds: 12,
    })
    await flush()

    await store.openOutputLocation()

    expect(mockOpenOutputLocation).toHaveBeenCalledTimes(1)
    expect(mockOpenOutputLocation).toHaveBeenCalledWith('D:/output/final')
  })
})
