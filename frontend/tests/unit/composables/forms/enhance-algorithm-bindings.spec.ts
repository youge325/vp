import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { createEnhanceAlgorithmBindings } from '@/composables/forms/enhance-algorithm-bindings'
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
    tensorEngines: { pytorch: ['cuda'], paddle: ['cuda'], onnx: ['cuda'] },
    interpolationAlgorithms: [
      { name: 'rife', tensorBackends: ['pytorch', 'onnx'], models: ['4.25'], onnxModels: ['rife.onnx'] },
      { name: 'rife-lite', tensorBackends: ['pytorch'], models: ['lite'], onnxModels: [] },
    ],
    superResolutionAlgorithms: [
      { name: 'placeholder', tensorBackends: ['onnx'], models: [], onnxModels: ['sr.onnx'], scaleFactors: [2] },
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
  const bindings = createEnhanceAlgorithmBindings({
    workflow: computed(() => workflow),
    checkResult: computed(() => checkResult.value),
  })
  return { bindings, workflow }
}

describe('enhance algorithm bindings', () => {
  it('derives backend-filtered algorithm and model lists', () => {
    const { bindings } = makeBindings()

    expect(bindings.interpolationAlgorithms.value.map((algorithm) => algorithm.name)).toEqual(['rife', 'rife-lite'])
    expect(bindings.interpolationModels.value).toEqual(['4.25'])
    expect(bindings.interpolationOnnxModels.value).toEqual(['rife.onnx'])
    expect(bindings.superResolutionAlgorithms.value.map((algorithm) => algorithm.name)).toEqual(['placeholder'])
    expect(bindings.superResolutionOnnxModels.value).toEqual(['sr.onnx'])
    expect(bindings.currentInterpolationAlgorithm.value?.name).toBe('rife')
  })

  it('tracks backend-derived state without workflow mutation rules', () => {
    const { bindings, workflow } = makeBindings()

    workflow.interpolation.tensorBackend = 'onnx'
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.algorithm = 'edvr'

    expect(bindings.isInterpolationOnnxBackend.value).toBe(true)
    expect(bindings.isSuperResolutionOnnxBackend.value).toBe(false)
    expect(bindings.interpolationAlgorithms.value.map((algorithm) => algorithm.name)).toEqual(['rife'])
    expect(bindings.superResolutionAlgorithms.value.map((algorithm) => algorithm.name)).toEqual(['edvr'])
    expect(bindings.currentSuperResolutionAlgorithm.value?.name).toBe('edvr')
  })
})
