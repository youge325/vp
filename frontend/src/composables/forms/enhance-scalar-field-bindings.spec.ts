import { computed, reactive } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { createEnhanceScalarFieldBindings } from './enhance-scalar-field-bindings'
import type { WorkflowConfig } from '@/types/protocol'

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfigForEnvironment(null)) as WorkflowConfig
  const scalarBindings = createEnhanceScalarFieldBindings({
    workflow: computed(() => workflow),
    patchWorkflow: (mutator) => { mutator(workflow) },
  })
  return { scalarBindings, workflow }
}

describe('enhance scalar field bindings', () => {
  it('writes interpolation, super-resolution, process order, and anime scalar fields', () => {
    const { scalarBindings, workflow } = makeBindings()

    scalarBindings.interpolationEngine.value = 'tensorrt'
    scalarBindings.interpolationModel.value = 'lite'
    scalarBindings.interpolationOnnxModel.value = 'rife.onnx'
    scalarBindings.fpsMode.value = 'multi'
    scalarBindings.targetFps.value = 72
    scalarBindings.interpolationMulti.value = 4
    scalarBindings.interpolationScale.value = 0.5
    scalarBindings.interpolationFp16.value = true
    scalarBindings.superResolutionEngine.value = 'tensorrt'
    scalarBindings.superResolutionOnnxModel.value = 'sr.onnx'
    scalarBindings.processOrder.value = 'super_resolution_first'
    scalarBindings.animeEnabled.value = true
    scalarBindings.animeProfile.value = 'line-art'
    scalarBindings.animeDenoise.value = 0.25
    scalarBindings.animeEdgeBoost.value = 1.5

    expect(workflow.interpolation).toMatchObject({
      engine: 'tensorrt',
      model: 'lite',
      onnxModel: 'rife.onnx',
      targetFps: 72,
      multi: 4,
      scale: 0.5,
      fp16: true,
    })
    expect(workflow.superResolution).toMatchObject({
      engine: 'tensorrt',
      onnxModel: 'sr.onnx',
    })
    expect(workflow.fpsMode).toBe('multi')
    expect(workflow.processOrder).toBe('super_resolution_first')
    expect(workflow.anime).toMatchObject({
      enabled: true,
      profile: 'line-art',
      denoise: 0.25,
      edgeBoost: 1.5,
    })
  })
})
