import { computed, reactive } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import { createEnhanceViewBindings } from '@/composables/forms/enhance-view-bindings'
import type { AlgorithmInfo } from '@/types/protocol'
import type { WorkflowConfig } from '@/types/protocol'
import { createEdvrAlgorithm, createRifeAlgorithm } from '../../fixtures/environment'

const rife: AlgorithmInfo = createRifeAlgorithm()
const edvr: AlgorithmInfo = createEdvrAlgorithm()

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfigForEnvironment(null)) as WorkflowConfig
  workflow.interpolation.enabled = true
  workflow.interpolation.algorithm = 'rife'
  workflow.interpolation.model = '4.25'
  workflow.superResolution.enabled = true
  workflow.superResolution.tensorBackend = 'paddle'
  workflow.superResolution.algorithm = 'edvr'
  workflow.superResolution.numFrames = 10

  const bindings = createEnhanceViewBindings({
    workflow: computed(() => workflow),
    activeVideoDimensions: computed(() => ({ width: 640, height: 288 })),
    currentInterpolationAlgorithm: computed(() => rife),
    currentSuperResolutionAlgorithm: computed(() => edvr),
  })
  return { bindings }
}

describe('enhance view bindings', () => {
  it('projects enhance view-model rows and interpolation model details', () => {
    const { bindings } = makeBindings()

    expect(bindings.currentInterpolationModelDetail.value?.name).toBe('4.25')
    expect(bindings.interpolationMetricRows.value.length).toBeGreaterThan(0)
    expect(bindings.superResolutionMetricRows.value.length).toBeGreaterThan(0)
    expect(bindings.superResolutionFixedWindowRows.value).toEqual([
      { label: '邻帧窗口', value: '5 帧（固定）' },
    ])
  })

  it('centralizes fixed input-frame copy and effective frame projection', () => {
    const { bindings } = makeBindings()

    expect(bindings.superResolutionInputFramesLabel).toBe('每块输入帧数')
    expect(bindings.superResolutionInputFramesHint).toContain('连续输入帧数')
    expect(bindings.isPaddleGanSuperResolution.value).toBe(true)
    expect(bindings.isSuperResolutionInputFramesEditable.value).toBe(false)
    expect(bindings.effectiveSuperResolutionNumFrames.value).toBe(5)
  })
})
