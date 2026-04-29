import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { WorkbenchPreset, WorkflowConfig } from '@/types'

const mediaStoreState = vi.hoisted(() => ({ current: null as any }))
const presetStoreState = vi.hoisted(() => ({ current: null as any }))
const envStoreState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/env', () => ({
  useEnvStore: () => envStoreState.current,
}))

vi.mock('@/stores/media', () => ({
  useMediaStore: () => mediaStoreState.current,
}))

vi.mock('@/stores/preset', () => ({
  usePresetStore: () => presetStoreState.current,
}))

import EnhanceModuleView from '@/views/EnhanceModuleView.vue'

function createWorkflowConfig(): WorkflowConfig {
  return {
    fpsMode: 'target',
    processOrder: 'super_resolution_then_interpolation',
    interpolation: {
      enabled: true,
      targetFps: 60,
      multi: 2,
      model: '4.25',
      onnxModel: '',
      scale: 1,
      fp16: false,
      tensorBackend: 'pytorch',
    },
    superResolution: {
      enabled: false,
      scaleFactor: 2,
      algorithm: 'placeholder',
      onnxModel: '',
    },
    anime: {
      enabled: false,
      profile: 'clean-lines',
      denoise: 10,
      edgeBoost: 15,
    },
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
      segmentFrames: 1000,
    },
    ...overrides,
  }
}

const sharedEditor = createEditor()

function createMediaStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    activeItem: null,
    editingScope: 'preset',
    editingSelectionCount: 0,
    editor: sharedEditor,
    ...overrides,
  }
}

function createPresetStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    draftPreset: sharedEditor,
    patchWorkflow: vi.fn((mutator: (config: WorkflowConfig) => void) => mutator(sharedEditor.workflowConfig)),
    ...overrides,
  }
}

function createEnvStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    env: {
      checkResult: {
        tensor_backends: {
          pytorch: true,
          paddle: true,
          onnx: true,
        },
        onnx_models: {
          interpolation: ['interp.onnx'],
          super_resolution: ['sr.onnx'],
        },
      },
    },
    ...overrides,
  }
}

describe('EnhanceModuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mediaStoreState.current = createMediaStoreMock()
    presetStoreState.current = createPresetStoreMock()
    envStoreState.current = createEnvStoreMock()
  })

  it('renders workflow controls even before media import', () => {
    const wrapper = mount(EnhanceModuleView)

    expect(wrapper.findAll('section')).toHaveLength(4)
    expect(wrapper.text()).toContain('默认预设')
    expect(wrapper.findAll('select').length).toBeGreaterThan(0)
  })

  it('forwards workflow edits through patchWorkflow', async () => {
    const wrapper = mount(EnhanceModuleView)

    const selects = wrapper.findAll('select')
    await selects[0]!.setValue('paddle')
    expect(presetStoreState.current.patchWorkflow).toHaveBeenCalled()
    expect(mediaStoreState.current.editor.workflowConfig.interpolation.tensorBackend).toBe('paddle')

    const checkboxes = wrapper.findAll('input[type="checkbox"]')
    await checkboxes[1]!.setValue(true)
    expect(mediaStoreState.current.editor.workflowConfig.interpolation.fp16).toBe(true)
  })

  it('shows ONNX backend and independent ONNX model selectors', async () => {
    const wrapper = mount(EnhanceModuleView)

    await wrapper.findAll('select')[0]!.setValue('onnx')

    expect(mediaStoreState.current.editor.workflowConfig.interpolation.tensorBackend).toBe('onnx')
    expect(mediaStoreState.current.editor.workflowConfig.interpolation.onnxModel).toBe('interp.onnx')
    expect(mediaStoreState.current.editor.workflowConfig.superResolution.onnxModel).toBe('sr.onnx')

    const onnxEditor = createEditor({
      workflowConfig: {
        ...createWorkflowConfig(),
        interpolation: {
          ...createWorkflowConfig().interpolation,
          tensorBackend: 'onnx',
          onnxModel: 'interp.onnx',
        },
        superResolution: {
          ...createWorkflowConfig().superResolution,
          onnxModel: 'sr.onnx',
        },
      },
    })
    mediaStoreState.current = createMediaStoreMock({ editor: onnxEditor })
    presetStoreState.current = createPresetStoreMock({ draftPreset: onnxEditor })

    const onnxWrapper = mount(EnhanceModuleView)
    expect(onnxWrapper.text()).toContain('ONNX 补帧模型')
    expect(onnxWrapper.text()).toContain('ONNX 超分模型')
  })
})
