import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { EncodeConfig, MediaItem, OutputConfig, WorkbenchPreset, WorkflowConfig } from '@/types'

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

import EncodeModuleView from '@/views/EncodeModuleView.vue'

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
      engine: 'cuda',
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
    preprocess: {
      enabled: false,
      filters: [],
    },
    postprocess: {
      enabled: false,
      filters: [],
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
    outputDir: 'D:/output',
    openOnComplete: true,
    segmentFrames: 1000,
  }
}

function createEditor(overrides: Partial<WorkbenchPreset> = {}): WorkbenchPreset {
  return {
    decodeConfig: {
      mode: 'hardware',
      hwaccel: 'cuda',
      hwaccelDevice: '',
      decoder: 'hevc_cuvid',
      options: {},
    },
    workflowConfig: createWorkflowConfig(),
    encodeConfig: createEncodeConfig(),
    outputConfig: createOutputConfig(),
    ...overrides,
  }
}

function createMediaItem(): MediaItem {
  const editor = createEditor()
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
      hasAudio: true,
      videoCodec: 'hevc',
    },
    issue: null,
    decodeConfig: editor.decodeConfig,
    workflowConfig: editor.workflowConfig,
    encodeConfig: editor.encodeConfig,
    outputConfig: editor.outputConfig,
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

const sharedEditor = createEditor()

function createEnvStoreMock() {
  return {
    env: { checkResult: null },
    operationIssue: null,
  }
}

function createMediaStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    activeItem: createMediaItem(),
    selectedIds: ['item-1'],
    editingScope: 'selection',
    editingSelectionCount: 1,
    editor: sharedEditor,
    ...overrides,
  }
}

function createPresetStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    draftPreset: sharedEditor,
    patchEncode: vi.fn((mutator: (config: EncodeConfig) => void) => mutator(sharedEditor.encodeConfig)),
    patchOutput: vi.fn((mutator: (config: OutputConfig) => void) => mutator(sharedEditor.outputConfig)),
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
    setActivePinia(createPinia())
    envStoreState.current = createEnvStoreMock()
    mediaStoreState.current = createMediaStoreMock()
    presetStoreState.current = createPresetStoreMock()
  })

  it('keeps output controls available in preset mode', () => {
    mediaStoreState.current = createMediaStoreMock({
      activeItem: null,
      selectedIds: [],
      editingScope: 'preset',
      editingSelectionCount: 0,
    })

    const wrapper = mount(EncodeModuleView)

    expect((wrapper.get('input[type="text"]').element as HTMLInputElement).value).toBe('D:/output')
    expect(wrapper.text()).toContain('默认预设')
  })

  it('updates output path and segment frames through patchOutput', async () => {
    const wrapper = mount(EncodeModuleView)

    const textInput = wrapper.get('input[type="text"]')
    await textInput.setValue('D:/custom-output')
    expect(presetStoreState.current.patchOutput).toHaveBeenCalled()
    expect(mediaStoreState.current.editor.outputConfig.outputDir).toBe('D:/custom-output')

    const numberInputs = wrapper.findAll('input[type="number"]')
    await numberInputs[0]!.setValue('240')
    expect(mediaStoreState.current.editor.outputConfig.segmentFrames).toBe(240)
  })

  it('lets the user pick an output directory before importing media', async () => {
    mediaStoreState.current = createMediaStoreMock({
      activeItem: null,
      selectedIds: [],
      editingScope: 'preset',
      editingSelectionCount: 0,
    })

    const wrapper = mount(EncodeModuleView)

    await wrapper.get('button').trigger('click')
    expect(presetStoreState.current.pickOutputDirectory).toHaveBeenCalledTimes(1)
  })
})
