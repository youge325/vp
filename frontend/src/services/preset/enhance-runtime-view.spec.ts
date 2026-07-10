import { describe, expect, it } from 'vitest'

import { buildEnhanceRuntimeView } from './enhance-runtime-view'
import { createDefaultWorkflowConfigForEnvironment } from './workflow-defaults'
import type { AlgorithmInfo, ModelVariantInfo } from '@/types/domain/env'

const interpolationDetail: ModelVariantInfo = {
  name: '4.25',
  label: 'RIFE 4.25',
  metrics: {
    parameterCount: 1,
    parameterBytes: 4,
    gflopsPerMegapixel: 10,
    activationBytesPerMegapixel: 1000,
    runtimeOverheadBytes: 100,
    inputModulo: 1,
    analysisStatus: 'ok',
    analysisNotes: [],
  },
}

const superResolutionDetail: ModelVariantInfo = {
  name: 'x4',
  label: 'EDVR',
  metrics: {
    parameterCount: 2,
    parameterBytes: 8,
    gflopsPerMegapixel: 20,
    activationBytesPerMegapixel: 2000,
    runtimeOverheadBytes: 200,
    runtimeFrameCount: 5,
    inputModulo: 1,
    analysisStatus: 'ok',
    analysisNotes: [],
  },
}

const fixedWindowAlgorithm: AlgorithmInfo = {
  name: 'edvr',
  family: 'paddlegan_vsr',
  tensorBackends: ['paddle'],
  models: ['x4'],
  fixedScaleFactor: 4,
  inputFrameMode: 'fixed_window',
  defaultNumFrames: 5,
}

describe('enhance runtime view', () => {
  it('builds runtime estimates, fixed-window rows, and combined VRAM rows', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.processOrder = 'super_resolution_then_interpolation'
    workflow.interpolation.enabled = true
    workflow.interpolation.scale = 1
    workflow.interpolation.fp16 = false
    workflow.superResolution.enabled = true
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 10

    const view = buildEnhanceRuntimeView({
      workflow,
      activeVideoDimensions: { width: 10, height: 5 },
      currentSuperResolutionAlgorithm: fixedWindowAlgorithm,
      currentInterpolationRuntimeDetail: interpolationDetail,
      currentSuperResolutionRuntimeDetail: superResolutionDetail,
      superResolutionRuntimeFrameCount: 5,
    })

    expect(view.interpolationInputDimensions).toEqual({ width: 40, height: 20 })
    expect(view.isPaddleGanSuperResolution).toBe(true)
    expect(view.isSuperResolutionInputFramesEditable).toBe(false)
    expect(view.effectiveSuperResolutionNumFrames).toBe(5)
    expect(view.superResolutionFixedWindowRows).toEqual([{ label: '邻帧窗口', value: '5 帧（固定）' }])
    expect(view.interpolationMetricRows[0].label).toBe('参数量')
    expect(view.superResolutionMetricRows[2].label).toBe('显存估算')
    expect(view.combinedPeakVramBytes).toBeGreaterThan(0)
    expect(view.combinedVramMetricRows).toHaveLength(1)
  })
})
