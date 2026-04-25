import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { useMediaStore } from '@/stores/media'
import { useTaskStore } from '@/stores/task'
import { cloneWorkflowConfig, createDefaultWorkbenchPreset, getVisibleDecoderProfiles } from '@/lib/task-mapper'
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
const mockPauseTask = vi.fn<() => Promise<void>>()
const mockResumeTask = vi.fn<() => Promise<void>>()
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
  pauseTask: () => mockPauseTask(),
  pickInputs: () => mockPickInputs(),
  pickOutputDirectory: () => mockPickOutputDirectory(),
  resumeTask: () => mockResumeTask(),
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
    resources: {
      output_dir: 'D:/default-output',
    },
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

async function bootstrapStores(): Promise<void> {
  const taskStore = useTaskStore()
  const presetStore = usePresetStore()
  const envStore = useEnvStore()
  await taskStore.attachTaskListeners()
  const hasPersistedPreset = await presetStore.loadPersistedPreset()
  await envStore.recheckEnvironment(false)
  if (!hasPersistedPreset && envStore.env.checkResult) {
    presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
  }
  presetStore.presetPersistenceReady = true
}

describe('workbench integration', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    setActivePinia(createPinia())
    handlersRef.current = null
    mockCheckEnvironment.mockReset()
    mockInspectVideo.mockReset()
    mockStartTask.mockReset()
    mockCancelTask.mockReset()
    mockPauseTask.mockReset()
    mockResumeTask.mockReset()
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
    mockPauseTask.mockResolvedValue()
    mockResumeTask.mockResolvedValue()
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
    await bootstrapStores()

    const envStore = useEnvStore()
    const mediaStore = useMediaStore()

    expect(mockLoadWorkbenchPreset).toHaveBeenCalledTimes(1)
    expect(mockCheckEnvironment).toHaveBeenCalledTimes(1)
    expect(mockCheckEnvironment).toHaveBeenCalledWith(false)
    expect(envStore.env.checkResult?.ffmpeg.available).toBe(true)
    expect(envStore.env.checkResult?.gpu.adapters[0]?.deviceType).toBe('discrete')
    expect(envStore.env.checkSource).toBe('probe')
    expect(envStore.env.lastProbeAt).toBe('2026-04-23T11:00:00Z')
    expect(mediaStore.editingScope).toBe('preset')
  })

  it('exposes editable draft presets before any media is imported', async () => {
    await bootstrapStores()

    const envStore = useEnvStore()
    const presetStore = usePresetStore()
    const mediaStore = useMediaStore()

    expect(mediaStore.activeItem).toBeNull()
    expect(mediaStore.editingScope).toBe('preset')
    expect(mediaStore.editor.decodeConfig.mode).toBe('hardware')
    expect(mediaStore.editor.decodeConfig.decoder).toBe('hevc_cuvid')
    expect(presetStore.draftPreset.workflowConfig.interpolation.enabled).toBe(true)
    expect(getVisibleDecoderProfiles(envStore.env.checkResult, '')).toHaveLength(3)
  })

  it('imports files without polluting env issues', async () => {
    await bootstrapStores()
    mockPickInputs.mockResolvedValueOnce(['D:/input/a.mp4'])

    const mediaStore = useMediaStore()
    const envStore = useEnvStore()
    await mediaStore.pickInputs()

    expect(mediaStore.mediaItems).toHaveLength(1)
    expect(envStore.env.issue).toBeNull()
    expect(envStore.operationIssue).toBeNull()
  })

  it('stores pickInputs failures as input operation issues', async () => {
    await bootstrapStores()
    mockPickInputs.mockRejectedValueOnce(new Error('pick_inputs not allowed'))

    const mediaStore = useMediaStore()
    const envStore = useEnvStore()
    await mediaStore.pickInputs()

    expect(envStore.env.issue).toBeNull()
    expect(envStore.operationIssue?.scope).toBe('input')
    expect(envStore.operationIssue?.error.code).toBe('pick_inputs_failed')
    expect(envStore.operationIssue?.error.message).toContain('pick_inputs')
  })

  it('keeps environment failures in env.issue', async () => {
    mockCheckEnvironment.mockRejectedValueOnce(new Error('ffmpeg missing'))

    const envStore = useEnvStore()
    await envStore.recheckEnvironment()

    expect(mockCheckEnvironment).toHaveBeenCalledWith(true)
    expect(envStore.env.issue?.code).toBe('check_failed')
    expect(envStore.operationIssue).toBeNull()
  })

  it('updates the draft preset and selected items together when workflow settings change', async () => {
    await bootstrapStores()
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    await mediaStore.addMediaPaths(['D:/input/a.mp4', 'D:/input/b.mp4', 'D:/input/c.mp4'])

    const [first, second, third] = mediaStore.mediaItems
    mediaStore.setActiveItem(first.id)
    mediaStore.setItemSelected(first.id, true)
    mediaStore.setItemSelected(second.id, true)
    mediaStore.setItemSelected(third.id, false)

    presetStore.patchWorkflow((config) => {
      config.interpolation.enabled = false
      config.anime.enabled = true
    })
    mediaStore.forEachEditableItem((item) => {
      const next = cloneWorkflowConfig(item.workflowConfig)
      next.interpolation.enabled = false
      next.anime.enabled = true
      item.workflowConfig = next
    })
    presetStore.schedulePresetSave()

    expect(presetStore.draftPreset.workflowConfig.interpolation.enabled).toBe(false)
    expect(presetStore.draftPreset.workflowConfig.anime.enabled).toBe(true)
    expect(first.workflowConfig.interpolation.enabled).toBe(false)
    expect(second.workflowConfig.interpolation.enabled).toBe(false)
    expect(third.workflowConfig.interpolation.enabled).toBe(true)
    expect(first.workflowConfig.anime.enabled).toBe(true)
    expect(second.workflowConfig.anime.enabled).toBe(true)
    expect(third.workflowConfig.anime.enabled).toBe(false)
  })

  it('imports new media with the persisted preset defaults', async () => {
    mockLoadWorkbenchPreset.mockResolvedValueOnce(makePreset())

    await bootstrapStores()
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    await mediaStore.addMediaPaths(['D:/input/a.mp4'])

    expect(mediaStore.mediaItems).toHaveLength(1)
    expect(presetStore.draftPreset.outputConfig.outputDir).toBe('D:/output/preset')
    expect(presetStore.draftPreset.workflowConfig.interpolation.enabled).toBe(false)
    expect(mediaStore.mediaItems[0]?.decodeConfig.hwaccelDevice).toBe('0')
    expect(mediaStore.mediaItems[0]?.workflowConfig.anime.enabled).toBe(true)
    expect(mediaStore.mediaItems[0]?.encodeConfig.container).toBe('mkv')
    expect(mediaStore.mediaItems[0]?.outputConfig.outputDir).toBe('D:/output/preset')
  })

  it('remaps persisted decoders to the same hardware family when the imported codec changes', async () => {
    mockLoadWorkbenchPreset.mockResolvedValueOnce(makePreset())

    await bootstrapStores()
    const mediaStore = useMediaStore()
    await mediaStore.addMediaPaths(['D:/input/h264-demo.mp4'])

    expect(mediaStore.mediaItems[0]?.info?.video_codec).toBe('h264')
    expect(mediaStore.mediaItems[0]?.decodeConfig.mode).toBe('hardware')
    expect(mediaStore.mediaItems[0]?.decodeConfig.hwaccel).toBe('cuda')
    expect(mediaStore.mediaItems[0]?.decodeConfig.hwaccelDevice).toBe('0')
    expect(mediaStore.mediaItems[0]?.decodeConfig.decoder).toBe('h264_cuvid')
  })

  it('forces a fresh environment probe when rechecking manually', async () => {
    await bootstrapStores()
    const envStore = useEnvStore()
    await envStore.recheckEnvironment()

    expect(mockCheckEnvironment).toHaveBeenNthCalledWith(1, false)
    expect(mockCheckEnvironment).toHaveBeenNthCalledWith(2, true)
  })

  it('persists preset edits with debounce while no media is selected', async () => {
    await bootstrapStores()
    const presetStore = usePresetStore()
    mockSaveWorkbenchPreset.mockClear()

    presetStore.patchOutput((config) => {
      config.outputDir = 'D:/output/debounced'
    })

    expect(mockSaveWorkbenchPreset).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(300)

    expect(mockSaveWorkbenchPreset).toHaveBeenCalledTimes(1)
    expect(mockSaveWorkbenchPreset.mock.calls[0]?.[0].outputConfig.outputDir).toBe('D:/output/debounced')
  })

  it('advances the batch queue and clears runtime artifacts after the batch finishes', async () => {
    await bootstrapStores()
    const mediaStore = useMediaStore()
    const taskStore = useTaskStore()
    await mediaStore.addMediaPaths(['D:/input/a.mp4', 'D:/input/b.mp4', 'D:/input/c.mp4'])
    await taskStore.attachTaskListeners()

    expect(handlersRef.current).not.toBeNull()

    await taskStore.startBatch()
    expect(taskStore.currentTaskItem?.displayName).toBe('a.mp4')
    expect(mockStartTask).toHaveBeenCalledTimes(1)

    handlersRef.current?.onCompleted({
      outputPath: 'D:/output/a_processed.mp4',
      processedFrames: 240,
      timeSeconds: 12,
    })
    await flush()

    expect(taskStore.batch.completedCount).toBe(1)
    expect(taskStore.currentTaskItem?.displayName).toBe('b.mp4')

    handlersRef.current?.onError({
      code: 'process_failed',
      message: 'boom',
      details: null,
    })
    await flush()

    expect(taskStore.batch.failedCount).toBe(1)
    expect(taskStore.currentTaskItem?.displayName).toBe('c.mp4')

    handlersRef.current?.onCancelled()
    await flush()

    expect(taskStore.batch.completedCount).toBe(0)
    expect(taskStore.batch.failedCount).toBe(0)
    expect(taskStore.batch.isRunning).toBe(false)
    expect(taskStore.currentTaskItem).toBeNull()
    expect(mediaStore.mediaItems.every((item) => item.taskState.status === 'idle')).toBe(true)
    expect(mediaStore.mediaItems.every((item) => item.lastOutputPath === '')).toBe(true)
    expect(mediaStore.mediaItems.every((item) => item.issue === null)).toBe(true)
  })

  it('pauses and resumes the current task through desktop IPC', async () => {
    await bootstrapStores()
    const mediaStore = useMediaStore()
    const taskStore = useTaskStore()
    await mediaStore.addMediaPaths(['D:/input/a.mp4'])

    await taskStore.startBatch()
    expect(taskStore.currentTaskItem?.taskState.status).toBe('running')

    await taskStore.pauseCurrentTask()

    expect(mockPauseTask).toHaveBeenCalledTimes(1)
    expect(taskStore.batch.isPaused).toBe(true)
    expect(taskStore.currentTaskItem?.taskState.status).toBe('paused')

    await taskStore.resumeCurrentTask()

    expect(mockResumeTask).toHaveBeenCalledTimes(1)
    expect(taskStore.batch.isPaused).toBe(false)
    expect(taskStore.currentTaskItem?.taskState.status).toBe('running')
  })

  it('interrupts the whole batch and does not continue to queued items', async () => {
    await bootstrapStores()
    const mediaStore = useMediaStore()
    const taskStore = useTaskStore()
    await mediaStore.addMediaPaths(['D:/input/a.mp4', 'D:/input/b.mp4'])
    await taskStore.attachTaskListeners()

    await taskStore.startBatch()
    expect(taskStore.currentTaskItem?.displayName).toBe('a.mp4')
    expect(taskStore.batch.queue).toHaveLength(1)

    await taskStore.interruptBatch()

    expect(mockCancelTask).toHaveBeenCalledTimes(1)
    expect(taskStore.batch.queue).toEqual([])
    expect(taskStore.batch.isCancelling).toBe(true)
    expect(taskStore.currentTaskItem?.taskState.status).toBe('cancelling')

    handlersRef.current?.onCancelled()
    await flush()

    expect(mockStartTask).toHaveBeenCalledTimes(1)
    expect(taskStore.batch.isRunning).toBe(false)
    expect(taskStore.batch.isCancelling).toBe(false)
    expect(taskStore.currentTaskItem).toBeNull()
  })

  it('surfaces task operation issues when pause or interrupt fails', async () => {
    await bootstrapStores()
    const mediaStore = useMediaStore()
    const taskStore = useTaskStore()
    const envStore = useEnvStore()
    await mediaStore.addMediaPaths(['D:/input/a.mp4'])

    await taskStore.startBatch()
    mockPauseTask.mockRejectedValueOnce(new Error('pause unsupported'))
    await taskStore.pauseCurrentTask()

    expect(envStore.operationIssue?.scope).toBe('task')
    expect(envStore.operationIssue?.error.code).toBe('pause_failed')
    expect(taskStore.currentTaskItem?.taskState.status).toBe('running')

    mockCancelTask.mockRejectedValueOnce(new Error('cancel unavailable'))
    await taskStore.interruptBatch()

    expect(envStore.operationIssue?.scope).toBe('task')
    expect(envStore.operationIssue?.error.code).toBe('cancel_failed')
    expect(taskStore.batch.isCancelling).toBe(false)
    expect(taskStore.currentTaskItem?.taskState.status).toBe('running')
  })
})
