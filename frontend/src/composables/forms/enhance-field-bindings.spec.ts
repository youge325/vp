import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfig } from '@/services/preset/workflow-defaults'
import { createEnhanceFieldBindings } from './enhance-field-bindings'
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
      { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'], onnxModels: ['rife.onnx'] },
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
      },
    ],
    animeProfiles: ['clean-lines', 'line-art'],
  }
}

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfig()) as WorkflowConfig
  const checkResult = ref<EnvironmentCheckResult | null>(makeEnv())
  const fieldBindings = createEnhanceFieldBindings({
    workflow: computed(() => workflow),
    checkResult: computed(() => checkResult.value),
    effectiveSuperResolutionNumFrames: computed(() =>
      workflow.superResolution.algorithm === 'edvr' ? 5 : workflow.superResolution.numFrames,
    ),
    patchWorkflow: (mutator) => { mutator(workflow) },
  })
  return { fieldBindings, workflow }
}

describe('enhance field bindings', () => {
  it('writes scalar workflow fields through draft bindings', () => {
    const { fieldBindings, workflow } = makeBindings()

    fieldBindings.interpolationEngine.value = 'tensorrt'
    fieldBindings.interpolationModel.value = 'lite'
    fieldBindings.interpolationOnnxModel.value = 'rife.onnx'
    fieldBindings.fpsMode.value = 'multi'
    fieldBindings.targetFps.value = 72
    fieldBindings.interpolationMulti.value = 4
    fieldBindings.interpolationScale.value = 0.5
    fieldBindings.interpolationFp16.value = true
    fieldBindings.processOrder.value = 'super_resolution_first'
    fieldBindings.animeEnabled.value = true
    fieldBindings.animeProfile.value = 'line-art'
    fieldBindings.animeDenoise.value = 0.25
    fieldBindings.animeEdgeBoost.value = 1.5

    expect(workflow.interpolation.engine).toBe('tensorrt')
    expect(workflow.interpolation.model).toBe('lite')
    expect(workflow.interpolation.onnxModel).toBe('rife.onnx')
    expect(workflow.fpsMode).toBe('multi')
    expect(workflow.interpolation.targetFps).toBe(72)
    expect(workflow.interpolation.multi).toBe(4)
    expect(workflow.interpolation.scale).toBe(0.5)
    expect(workflow.interpolation.fp16).toBe(true)
    expect(workflow.processOrder).toBe('super_resolution_first')
    expect(workflow.anime).toMatchObject({
      enabled: true,
      profile: 'line-art',
      denoise: 0.25,
      edgeBoost: 1.5,
    })
  })

  it('applies workflow mutation effects and exposes effective super-resolution frame count', () => {
    const { fieldBindings, workflow } = makeBindings()

    fieldBindings.interpolationEnabled.value = true
    fieldBindings.interpolationBackend.value = 'onnx'
    fieldBindings.superResolutionEnabled.value = true
    fieldBindings.superResolutionBackend.value = 'paddle'
    fieldBindings.superResolutionAlgorithm.value = 'edvr'
    fieldBindings.superResolutionScale.value = 2
    fieldBindings.superResolutionNumFrames.value = 10

    expect(workflow.interpolation.enabled).toBe(true)
    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.onnxModel).toBe('rife.onnx')
    expect(workflow.superResolution.enabled).toBe(true)
    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.algorithm).toBe('edvr')
    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(fieldBindings.superResolutionNumFrames.value).toBe(5)
  })
})
