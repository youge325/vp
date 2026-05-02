import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { CapabilityOptionSpec, DecodeConfig, MediaItem, WorkbenchPreset, WorkflowConfig, EncodeConfig, OutputConfig } from '@/types'

const envStoreState = vi.hoisted(() => ({ current: null as any }))
const mediaStoreState = vi.hoisted(() => ({ current: null as any }))
const presetStoreState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/env', () => ({
  useEnvStore: () => envStoreState.current,
}))

vi.mock('@/stores/media', () => ({
  useMediaStore: () => mediaStoreState.current,
}))

vi.mock('@/stores/preset', () => ({
  usePresetStore: () => presetStoreState.current,
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
  label: 'Deinterlace',
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

function createWorkflowConfig(): WorkflowConfig {
  return {
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
  }
}

function createEncodeConfig(): EncodeConfig {
  return {
    codec: 'hevc_nvenc',
    family: 'nvidia',
    container: 'mp4',
    keepAudio: true,
    rateControl: {
      mode: 'cq',
      value: 23,
    },
    options: {},
  }
}

function createOutputConfig(): OutputConfig {
  return {
    outputDir: '',
    openOnComplete: true,
    segmentFrames: 1000,
  }
}

function createDecodeConfig(): DecodeConfig {
  return {
    mode: 'hardware',
    hwaccel: 'cuda',
    hwaccelDevice: '',
    decoder: 'hevc_cuvid',
    options: {},
  }
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
    decodeConfig: createDecodeConfig(),
    workflowConfig: createWorkflowConfig(),
    encodeConfig: createEncodeConfig(),
    outputConfig: createOutputConfig(),
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
      resumeStatus: null,
    },
    lastOutputPath: '',
  }
}

function createEditor(overrides: Partial<WorkbenchPreset> = {}): WorkbenchPreset {
  return {
    decodeConfig: createDecodeConfig(),
    workflowConfig: createWorkflowConfig(),
    encodeConfig: createEncodeConfig(),
    outputConfig: createOutputConfig(),
    ...overrides,
  }
}

function createMediaStoreMock(overrides: Record<string, unknown> = {}) {
  const item = createMediaItem()
  return {
    activeItem: item,
    selectedIds: [item.id],
    editingScope: 'selection',
    editingSelectionCount: 1,
    editor: createEditor(),
    editorVideoCodec: 'hevc',
    ...overrides,
  }
}

function createEnvStoreMock() {
  return {
    env: {
      checkResult: {
        ffmpeg: { available: true, encoderProfiles: [], decoderProfiles: [softwareProfile, hardwareProfile] },
        gpu: { adapters: [] },
      },
    },
    operationIssue: null,
  }
}

function createPresetStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    setDecodeProfile: vi.fn(),
    setDecodeHwaccelDevice: vi.fn(),
    setDecodeOption: vi.fn(),
    getOptionValue: vi.fn((option, values) => values[option.name] ?? option.defaultValue ?? false),
    ...overrides,
  }
}

describe('DecodeModuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    envStoreState.current = createEnvStoreMock()
    mediaStoreState.current = createMediaStoreMock()
    presetStoreState.current = createPresetStoreMock()
  })

  it('renders preset controls even when there is no active item', () => {
    mediaStoreState.current = createMediaStoreMock({
      activeItem: null,
      selectedIds: [],
      editingScope: 'preset',
      editingSelectionCount: 0,
      editor: createEditor({
        decodeConfig: {
          mode: 'software',
          hwaccel: '',
          hwaccelDevice: '1',
          decoder: 'software',
          options: {},
        },
      }),
      editorVideoCodec: '',
    })

    const wrapper = mount(DecodeModuleView)

    expect(wrapper.find('select').exists()).toBe(true)
    expect((wrapper.find('input[type="text"]').element as HTMLInputElement).value).toBe('1')
    expect(wrapper.text()).toContain('默认预设')
  })

  it('renders decode controls and forwards interactions to the store', async () => {
    const wrapper = mount(DecodeModuleView)

    const select = wrapper.get('select').element as HTMLSelectElement
    select.value = 'software'
    await select.dispatchEvent(new Event('change'))
    expect(presetStoreState.current?.setDecodeProfile).toHaveBeenCalledWith('software')

    await wrapper.get('input[type="text"]').setValue('0')
    expect(presetStoreState.current?.setDecodeHwaccelDevice).toHaveBeenCalledWith('0')

    const checkbox = wrapper.find('input[type="checkbox"]')
    if (checkbox.exists()) {
      await checkbox.setValue(true)
      expect(presetStoreState.current?.setDecodeOption).toHaveBeenCalledWith('deint', true)
    }
  })
})
