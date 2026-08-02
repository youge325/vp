import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { createEnhanceAlgorithmBindings } from '@/composables/forms/enhance-algorithm-bindings'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import { createEnhanceEnvironment } from '../../fixtures/environment'

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfigForEnvironment(null)) as WorkflowConfig
  const checkResult = ref<EnvironmentCheckResult | null>(createEnhanceEnvironment())
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
    expect(bindings.interpolationOnnxModels.value).toEqual(['rife_v4.25.onnx'])
    expect(bindings.superResolutionAlgorithms.value.map((algorithm) => algorithm.name)).toEqual([
      'real-rawvsr-basicvsr',
      'real-rawvsr-edvr',
      'real-rawvsr-tdan',
      'real-rawvsr-toflow',
    ])
    expect(bindings.superResolutionOnnxModels.value).toEqual([])
    expect(bindings.currentInterpolationAlgorithm.value?.name).toBe('rife')
    expect(bindings.currentSuperResolutionAlgorithm.value?.scaleFactors).toEqual([2, 3, 4])
  })

  it('tracks backend-derived state without workflow mutation rules', () => {
    const { bindings, workflow } = makeBindings()

    workflow.interpolation.tensorBackend = 'onnx'
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.algorithm = 'edvr'

    expect(bindings.isInterpolationOnnxBackend.value).toBe(true)
    expect(bindings.isSuperResolutionOnnxBackend.value).toBe(false)
    expect(bindings.interpolationAlgorithms.value.map((algorithm) => algorithm.name)).toEqual([
      'rife',
      'onnx-only',
    ])
    expect(bindings.superResolutionAlgorithms.value.map((algorithm) => algorithm.name)).toEqual([
      'ppmsvsr',
      'edvr',
      'custom-vsr',
      'ppmsvsr-large',
      'basicvsr',
      'iconvsr',
      'basicvsr-plus-plus',
    ])
    expect(bindings.currentSuperResolutionAlgorithm.value?.name).toBe('edvr')
  })
})
