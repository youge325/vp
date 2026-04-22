import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useWorkbenchStore } from '@/stores/workbench'
import type { EnvironmentCheckResult, VideoInfoResult } from '@/types'

interface TaskEventHandlers {
  onProgress: (payload: Record<string, unknown>) => void
  onLog: (payload: Record<string, unknown>) => void
  onCompleted: (payload: Record<string, unknown>) => void
  onError: (payload: { code: string; message: string; details?: Record<string, unknown> | null }) => void
  onCancelled: () => void
}

const handlersRef: { current: TaskEventHandlers | null } = { current: null }

const mockCheckEnvironment = vi.fn<() => Promise<EnvironmentCheckResult>>()
const mockInspectVideo = vi.fn<(inputPath: string) => Promise<VideoInfoResult>>()
const mockStartTask = vi.fn<(request: unknown) => Promise<void>>()
const mockCancelTask = vi.fn<() => Promise<void>>()
const mockPickInputs = vi.fn<() => Promise<string[]>>()
const mockPickOutputDirectory = vi.fn<() => Promise<string | null>>()
const mockOpenOutputLocation = vi.fn<(path: string) => Promise<void>>()
const mockOpenFileOrDirectory = vi.fn<(path: string) => Promise<void>>()

vi.mock('@/lib/tauri', () => ({
  cancelTask: () => mockCancelTask(),
  checkEnvironment: () => mockCheckEnvironment(),
  inspectVideo: (inputPath: string) => mockInspectVideo(inputPath),
  listenTaskEvents: async (handlers: TaskEventHandlers) => {
    handlersRef.current = handlers
    return () => {
      handlersRef.current = null
    }
  },
  openFileOrDirectory: (path: string) => mockOpenFileOrDirectory(path),
  openOutputLocation: (path: string) => mockOpenOutputLocation(path),
  pickInputs: () => mockPickInputs(),
  pickOutputDirectory: () => mockPickOutputDirectory(),
  startTask: (request: unknown) => mockStartTask(request),
}))

function makeEnv(): EnvironmentCheckResult {
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

function makeVideoInfo(inputPath: string): VideoInfoResult {
  return {
    type: 'info',
    fps: 24,
    frames: 240,
    duration: 10,
    width: inputPath.includes('4k') ? 3840 : 1920,
    height: inputPath.includes('4k') ? 2160 : 1080,
    has_audio: true,
    video_codec: 'hevc',
  }
}

async function flush(): Promise<void> {
  await Promise.resolve()
  await Promise.resolve()
}

describe('workbench store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    handlersRef.current = null
    mockCheckEnvironment.mockReset()
    mockInspectVideo.mockReset()
    mockStartTask.mockReset()
    mockCancelTask.mockReset()
    mockPickInputs.mockReset()
    mockPickOutputDirectory.mockReset()
    mockOpenOutputLocation.mockReset()
    mockOpenFileOrDirectory.mockReset()
    mockCheckEnvironment.mockResolvedValue(makeEnv())
    mockInspectVideo.mockImplementation(async (inputPath: string) => makeVideoInfo(inputPath))
    mockStartTask.mockResolvedValue()
    mockCancelTask.mockResolvedValue()
    mockPickInputs.mockResolvedValue([])
    mockPickOutputDirectory.mockResolvedValue(null)
    mockOpenOutputLocation.mockResolvedValue()
    mockOpenFileOrDirectory.mockResolvedValue()
  })

  it('bootstraps environment probing on startup', async () => {
    const store = useWorkbenchStore()

    await store.bootstrap()

    expect(mockCheckEnvironment).toHaveBeenCalledTimes(1)
    expect(store.env.checkResult?.ffmpeg.available).toBe(true)
    expect(store.env.checkResult?.gpu.adapters[0]?.deviceType).toBe('discrete')
  })

  it('applies workflow edits only to active item and selected items', async () => {
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

    expect(first.workflowConfig.interpolation.enabled).toBe(false)
    expect(second.workflowConfig.interpolation.enabled).toBe(false)
    expect(third.workflowConfig.interpolation.enabled).toBe(true)
    expect(first.workflowConfig.anime.enabled).toBe(true)
    expect(second.workflowConfig.anime.enabled).toBe(true)
    expect(third.workflowConfig.anime.enabled).toBe(false)
  })

  it('advances the batch queue across completed, error, and cancelled events', async () => {
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

    expect(store.batch.completedIds).toHaveLength(1)
    expect(store.currentTaskItem?.displayName).toBe('b.mp4')

    handlersRef.current?.onError({
      code: 'process_failed',
      message: 'boom',
      details: null,
    })
    await flush()

    expect(store.batch.failedIds).toHaveLength(1)
    expect(store.currentTaskItem?.displayName).toBe('c.mp4')

    handlersRef.current?.onCancelled()
    await flush()

    expect(store.batch.failedIds).toHaveLength(2)
    expect(store.batch.isRunning).toBe(false)
    expect(store.currentTaskItem).toBeNull()
  })
})
