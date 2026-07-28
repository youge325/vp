import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { createEnhanceFormBindings } from '@/composables/forms/enhance-form-bindings'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import { createEnhanceEnvironment } from '../../fixtures/environment'

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfigForEnvironment(null)) as WorkflowConfig
  const checkResult = ref<EnvironmentCheckResult | null>(createEnhanceEnvironment())
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
    expect(form.superResolutionInputFramesLabel).toBe('每块输入帧数')
    expect(form.superResolutionInputFramesHint).toContain('连续输入帧数')
    expect(form.currentInterpolationModelDetail?.name).toBe('4.25')
  })

  it('applies workflow mutations through writable bindings while preserving return fields', () => {
    const { form, workflow } = makeBindings()

    form.interpolationBackend = 'onnx'
    expect(workflow.interpolation.tensorBackend).toBe('onnx')
    expect(form.isInterpolationOnnxBackend).toBe(true)
    expect(form.interpolationOnnxModel).toBe('rife_v4.25.onnx')

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
