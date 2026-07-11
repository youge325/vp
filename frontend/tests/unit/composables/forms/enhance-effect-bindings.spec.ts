import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { createEnhanceEffectBindings } from '@/composables/forms/enhance-effect-bindings'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import { createEnvironmentResult } from '../../fixtures/environment'

function makeEnv(): EnvironmentCheckResult {
  return createEnvironmentResult({
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda', 'tensorrt'], onnx: ['cuda', 'tensorrt'] },
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
    runtimeMode: 'bundled',
  })
}

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfigForEnvironment(null)) as WorkflowConfig
  const checkResult = ref<EnvironmentCheckResult | null>(makeEnv())
  const effectBindings = createEnhanceEffectBindings({
    workflow: computed(() => workflow),
    checkResult: computed(() => checkResult.value),
    effectiveSuperResolutionNumFrames: computed(() =>
      workflow.superResolution.algorithm === 'edvr' ? 5 : workflow.superResolution.numFrames,
    ),
    patchWorkflow: (mutator) => { mutator(workflow) },
  })
  return { effectBindings, workflow }
}

describe('enhance effect bindings', () => {
  it('applies workflow mutation effects while reading effective super-resolution frame count', () => {
    const { effectBindings, workflow } = makeBindings()

    effectBindings.interpolationEnabled.value = true
    effectBindings.interpolationBackend.value = 'onnx'
    effectBindings.interpolationAlgorithm.value = 'rife'
    effectBindings.superResolutionEnabled.value = true
    effectBindings.superResolutionBackend.value = 'paddle'
    effectBindings.superResolutionAlgorithm.value = 'edvr'
    effectBindings.superResolutionScale.value = 2
    effectBindings.superResolutionNumFrames.value = 10

    expect(workflow.interpolation.enabled).toBe(true)
    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(workflow.interpolation.algorithm).toBe('rife')
    expect(workflow.interpolation.onnxModel).toBe('rife.onnx')
    expect(workflow.superResolution.enabled).toBe(true)
    expect(workflow.superResolution.tensorBackend).toBe('paddle')
    expect(workflow.superResolution.algorithm).toBe('edvr')
    expect(workflow.superResolution.scaleFactor).toBe(4)
    expect(effectBindings.superResolutionNumFrames.value).toBe(5)
  })
})
