import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MediaItem } from '@/types'

const storeState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/workbench', () => ({
  useWorkbenchStore: () => storeState.current,
}))

import EncodeModuleView from '@/views/EncodeModuleView.vue'

function createMediaItem(): MediaItem {
  return {
    id: 'item-1',
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
    decodeConfig: {
      mode: 'hardware',
      hwaccel: 'cuda',
      hwaccelDevice: '',
      decoder: 'hevc_cuvid',
      options: {},
    },
    workflowConfig: {
      fpsMode: 'target',
      processOrder: 'super_resolution_then_interpolation',
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
        enabled: false,
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
    encodeConfig: {
      codec: 'hevc_nvenc',
      family: 'nvidia',
      container: 'mp4',
      keepAudio: true,
      rateControl: {
        mode: 'cq',
        value: 23,
      },
      options: {},
    },
    outputConfig: {
      outputDir: 'D:/output',
      openOnComplete: true,
      segmentFrames: 1000,
    },
    taskState: {
      status: 'idle',
      percent: 0,
      current: 0,
      total: 0,
      stage: '',
      stageIndex: 0,
      stageTotal: 0,
      logs: [],
      outputPath: '',
      processedFrames: 0,
      timeSeconds: 0,
      error: null,
      startedAt: null,
      finishedAt: null,
    },
    lastOutputPath: '',
  }
}

function createStoreMock(overrides: Record<string, unknown> = {}) {
  const item = createMediaItem()
  return {
    activeItem: item,
    selectedIds: [item.id],
    operationIssue: null,
    visibleEncoderProfiles: [
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
    currentEncoderProfile: {
      name: 'hevc_nvenc',
      label: 'NVENC H.265',
      family: 'nvidia',
      codec: 'hevc',
      available: true,
      pixelFormats: ['p010le'],
      hardwareDevices: ['cuda'],
      options: [],
    },
    patchEncode: vi.fn((mutator: (config: MediaItem['encodeConfig']) => void) => mutator(item.encodeConfig)),
    patchOutput: vi.fn((mutator: (config: MediaItem['outputConfig']) => void) => mutator(item.outputConfig)),
    setEncodeRateControlMode: vi.fn(),
    setEncodeRateControlValue: vi.fn(),
    setEncodeProfile: vi.fn(),
    setEncodeOption: vi.fn(),
    pickOutputDirectory: vi.fn(),
    getOptionValue: vi.fn(),
    ...overrides,
  }
}

describe('EncodeModuleView', () => {
  beforeEach(() => {
    storeState.current = createStoreMock()
  })

  it('updates output path and segment frames through patchOutput', async () => {
    const wrapper = mount(EncodeModuleView)

    const textInput = wrapper.get('input[type="text"]')
    await textInput.setValue('D:/custom-output')
    expect(storeState.current.patchOutput).toHaveBeenCalled()
    expect(storeState.current.activeItem.outputConfig.outputDir).toBe('D:/custom-output')

    const numberInputs = wrapper.findAll('input[type="number"]')
    await numberInputs[0]!.setValue('240')
    expect(storeState.current.activeItem.outputConfig.segmentFrames).toBe(240)
  })
})
