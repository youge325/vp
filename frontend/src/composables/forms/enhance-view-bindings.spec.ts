import { computed, reactive } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfig } from '@/services/preset/defaults'
import { createEnhanceViewBindings } from './enhance-view-bindings'
import type { AlgorithmInfo } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'

const rife: AlgorithmInfo = {
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
}

const edvr: AlgorithmInfo = {
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
}

function makeBindings() {
  const workflow = reactive(createDefaultWorkflowConfig()) as WorkflowConfig
  workflow.interpolation.enabled = true
  workflow.interpolation.algorithm = 'rife'
  workflow.interpolation.model = '4.25'
  workflow.superResolution.enabled = true
  workflow.superResolution.tensorBackend = 'paddle'
  workflow.superResolution.algorithm = 'edvr'
  workflow.superResolution.model = 'x4'
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
  it('projects enhance view-model rows and selected model details', () => {
    const { bindings } = makeBindings()

    expect(bindings.currentInterpolationModelDetail.value?.name).toBe('4.25')
    expect(bindings.currentSuperResolutionModelDetail.value?.name).toBe('x4')
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
