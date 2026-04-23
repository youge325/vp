import { describe, expect, it } from 'vitest'
import {
  buildTaskRequest,
  createDefaultDecodeConfig,
  createDefaultEncodeConfig,
  resolvePrimaryMode,
} from '@/lib/task-mapper'
import { createIdleTaskState } from '@/lib/task-events'
import type { EnvironmentCheckResult, MediaItem } from '@/types'

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
        {
          name: 'libx265',
          label: 'CPU H.265',
          family: 'cpu',
          codec: 'hevc',
          available: true,
          pixelFormats: ['yuv420p10le'],
          hardwareDevices: [],
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
          deviceType: 'discrete',
          adapterCompatibility: 'NVIDIA',
          driverVersion: '1',
        },
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

function makeItem(env = makeEnv()): MediaItem {
  return {
    id: 'demo',
    inputPath: 'D:/input/demo.mp4',
    displayName: 'demo.mp4',
    selected: true,
    inspecting: false,
    info: {
      type: 'info',
      fps: 24,
      frames: 240,
      duration: 10,
      width: 1920,
      height: 1080,
      has_audio: true,
      video_codec: 'hevc',
    },
    issue: null,
    decodeConfig: createDefaultDecodeConfig(env, 'hevc'),
    workflowConfig: {
      fpsMode: 'target',
      processOrder: 'frame_interpolation_then_super_resolution',
      interpolation: {
        enabled: true,
        targetFps: 60,
        multi: 2,
        model: '4.25',
        scale: 1,
        fp16: false,
        tensorBackend: 'pytorch',
      },
      superResolution: {
        enabled: true,
        scaleFactor: 2,
        algorithm: 'placeholder',
      },
      anime: {
        enabled: false,
        profile: 'clean-lines',
        denoise: 10,
        edgeBoost: 15,
      },
    },
    encodeConfig: createDefaultEncodeConfig(env),
    outputConfig: {
      outputDir: 'D:/output',
      openOnComplete: true,
      segmentFrames: 1000,
    },
    taskState: createIdleTaskState(),
    lastOutputPath: '',
  }
}

describe('task mapper', () => {
  it('derives the primary mode from nested workflow switches', () => {
    const item = makeItem()
    expect(resolvePrimaryMode(item)).toBe('frame_interpolation')

    item.workflowConfig.interpolation.enabled = false
    expect(resolvePrimaryMode(item)).toBe('super_resolution')

    item.workflowConfig.superResolution.enabled = false
    item.workflowConfig.anime.enabled = true
    expect(resolvePrimaryMode(item)).toBe('anime_optimization')

    item.workflowConfig.anime.enabled = false
    expect(resolvePrimaryMode(item)).toBe('format_conversion')
  })

  it('builds nested task requests without legacy desktop-only fields', () => {
    const item = makeItem()
    const request = buildTaskRequest(item)
    const legacyTempField = ['temp', 'Dir'].join('')

    expect(request.inputPath).toBe('D:/input/demo.mp4')
    expect(request.decodeConfig.decoder).toBe('hevc_cuvid')
    expect(request.workflowConfig.interpolation.targetFps).toBe(60)
    expect(request.encodeConfig.codec).toBe('hevc_nvenc')
    expect(request.outputConfig.outputDir).toBe('D:/output')
    expect(request.outputConfig.segmentFrames).toBe(1000)
    expect(request).not.toHaveProperty('outputPath')
    expect(request).not.toHaveProperty(legacyTempField)
  })
})
