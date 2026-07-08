import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfig } from '@/services/preset/workflow-defaults'
import { createEnhanceFormBindings } from './enhance-form-bindings'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'

function makeEnv(): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { available: true, devices: ['GPU'], adapters: [], cudaAvailable: true },
    tensorBackends: { pytorch: true, paddle: true, onnx: true },
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda', 'tensorrt'], onnx: ['cuda', 'tensorrt'] },
    onnxRuntime: { available: true, providers: ['CUDAExecutionProvider'] },
    rifeModel: { available: true, version: '4.25' },
    interpolationAlgorithms: [
      {
        name: 'rife',
        tensorBackends: ['pytorch', 'onnx'],
        models: ['4.25'],
        onnxModels: ['rife.onnx'],
        modelDetails: [
          {
            name: '4.25',
            label: 'RIFE 4.25',
            metrics: {
              parameterCount: 5670892,
              parameterBytes: 22683568,
              gflopsPerMegapixel: 18.5,
              activationBytesPerMegapixel: 694800000,
              runtimeOverheadBytes: 38000000,
              inputModulo: 64,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
      },
      { name: 'rife-lite', tensorBackends: ['pytorch'], models: ['lite'], onnxModels: [] },
    ],
    superResolutionAlgorithms: [
      { name: 'placeholder', tensorBackends: ['onnx'], models: [], onnxModels: ['sr.onnx'], scaleFactors: [2] },
      {
        name: 'ppmsvsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        fixedScaleFactor: 4,
        inputFrameMode: 'editable_chunk',
        defaultNumFrames: 10,
      },
      {
        name: 'edvr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        fixedScaleFactor: 4,
        inputFrameMode: 'fixed_window',
        defaultNumFrames: 5,
        modelDetails: [
          {
            name: 'x4',
            label: 'EDVR',
            metrics: {
              parameterCount: 20633827,
              parameterBytes: 82535308,
              gflopsPerMegapixel: 240,
              activationBytesPerMegapixel: 1000,
              runtimeOverheadBytes: 100,
              runtimeFrameCount: 5,
              inputModulo: 4,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
      },
    ],
    animeProfiles: ['clean-lines', 'line-art'],
  }
}

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfig()) as WorkflowConfig
  const checkResult = ref<EnvironmentCheckResult | null>(makeEnv())
  const activeVideoDimensions = ref({ width: 640, height: 288 })
  const form = createEnhanceFormBindings({
    workflow: computed(() => workflow),
    checkResult: computed(() => checkResult.value),
    activeVideoDimensions: computed(() => activeVideoDimensions.value),
    patchWorkflow: (mutator) => { mutator(workflow) },
  })
  return { form, workflow }
}

describe('enhance form bindings', () => {
  it('exposes existing algorithm lists, static input-frame copy, and view-model projections', () => {
    const { form } = makeBindings()

    expect(form.interpolationAlgorithms.map((algorithm) => algorithm.name)).toEqual(['rife', 'rife-lite'])
    expect(form.superResolutionAlgorithms.map((algorithm) => algorithm.name)).toEqual(['placeholder'])
    expect(form.animeProfiles).toEqual(['clean-lines', 'line-art'])
    expect(form.superResolutionInputFramesLabel).toBe('每块输入帧数')
    expect(form.superResolutionInputFramesHint).toContain('连续输入帧数')
    expect(form.currentInterpolationModelDetail?.name).toBe('4.25')
  })

  it('applies workflow mutations through writable bindings while preserving return fields', () => {
    const { form, workflow } = makeBindings()

    form.interpolationBackend = 'onnx'
    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(form.isInterpolationOnnxBackend).toBe(true)
    expect(form.interpolationOnnxModel).toBe('rife.onnx')

    form.superResolutionBackend = 'paddle'
    form.superResolutionAlgorithm = 'edvr'
    form.superResolutionNumFrames = 10

    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.algorithm).toBe('edvr')
    expect(form.isPaddleGanSuperResolution).toBe(true)
    expect(form.superResolutionNumFrames).toBe(5)
    expect(form.isSuperResolutionInputFramesEditable).toBe(false)
    expect(form.superResolutionFixedWindowRows).toEqual([
      { label: '邻帧窗口', value: '5 帧（固定）' },
    ])
  })
})
