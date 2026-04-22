import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CapabilityOptionSpec, MediaItem } from '@/types'

const storeState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/workbench', () => ({
  useWorkbenchStore: () => storeState.current,
}))

import DecodeModuleView from '@/views/DecodeModuleView.vue'

const softwareProfile = {
  name: 'software',
  label: 'Software Decode',
  family: 'software' as const,
  codec: 'any',
  available: true,
  pixelFormats: [],
  hardwareDevices: [],
  options: [],
}

const booleanOption: CapabilityOptionSpec = {
  name: 'deint',
  label: '去隔行',
  type: 'boolean',
  defaultValue: false,
  choices: [],
  min: null,
  max: null,
}

const hardwareProfile = {
  name: 'hevc_cuvid',
  label: 'NVDEC H.265',
  family: 'nvidia' as const,
  codec: 'hevc',
  available: true,
  pixelFormats: [],
  hardwareDevices: ['cuda'],
  options: [booleanOption],
}

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
      outputDir: '',
      openOnComplete: true,
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
  return {
    ...createStoreMockBase(),
    ...overrides,
  }
}

function createStoreMockBase() {
  const item = createMediaItem()
  return {
    activeItem: item,
    selectedIds: [item.id],
    currentDecoderProfile: hardwareProfile,
    visibleDecoderProfiles: [softwareProfile, hardwareProfile],
    setDecodeProfile: vi.fn(),
    setDecodeHwaccelDevice: vi.fn(),
    setDecodeOption: vi.fn(),
    getOptionValue: (option: CapabilityOptionSpec, values: Record<string, string | number | boolean>) =>
      option.name in values ? values[option.name] : option.defaultValue ?? false,
  }
}

describe('DecodeModuleView', () => {
  beforeEach(() => {
    storeState.current = createStoreMock()
  })

  it('shows an empty state when there is no active item', () => {
    storeState.current = createStoreMock({
      activeItem: null,
      selectedIds: [],
      currentDecoderProfile: null,
      visibleDecoderProfiles: [],
    })

    const wrapper = mount(DecodeModuleView)

    expect(wrapper.text()).toContain('还没有激活文件')
    expect(wrapper.text()).not.toContain('解码参数')
  })

  it('renders decode controls and forwards interactions to the store', async () => {
    const wrapper = mount(DecodeModuleView)

    expect(wrapper.text()).toContain('解码设置')
    expect(wrapper.find('.stats-grid').exists()).toBe(false)
    expect(wrapper.findAll('.stat-card')).toHaveLength(0)

    await wrapper.get('select').setValue('software')
    expect(storeState.current?.setDecodeProfile).toHaveBeenCalledWith('software')

    await wrapper.get('input[type="text"]').setValue('0')
    expect(storeState.current?.setDecodeHwaccelDevice).toHaveBeenCalledWith('0')

    await wrapper.get('input[type="checkbox"]').setValue(true)
    expect(storeState.current?.setDecodeOption).toHaveBeenCalledWith('deint', true)
  })
})
