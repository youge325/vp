import { describe, expect, it } from 'vitest'

import { buildEnhanceRuntimeFrameState, buildEnhanceRuntimeRows } from '@/services/preset/enhance-runtime-rows'
import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import type { AlgorithmInfo, ModelVariantInfo } from '@/types/protocol'
import type { RuntimeMetricEstimate } from '@/types/view/model-metrics'

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

const estimate: RuntimeMetricEstimate = {
  effectiveWidth: 10,
  effectiveHeight: 5,
  megapixels: 0.00005,
  gflops: 1.5,
  vramBytes: 256,
}

describe('enhance runtime rows', () => {
  it('builds fixed-window, metric, and combined VRAM rows', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.interpolation.enabled = true
    workflow.superResolution.enabled = true
    workflow.superResolution.numFrames = 10

    const rows = buildEnhanceRuntimeRows({
      workflow,
      frameState: buildEnhanceRuntimeFrameState({
        workflow,
        currentSuperResolutionAlgorithm: fixedWindowAlgorithm,
      }),
      currentInterpolationRuntimeDetail: interpolationDetail,
      currentSuperResolutionRuntimeDetail: superResolutionDetail,
      interpolationRuntimeEstimate: estimate,
      superResolutionRuntimeEstimate: estimate,
      combinedPeakVramBytes: 256,
    })

    expect(rows.isPaddleGanSuperResolution).toBe(true)
    expect(rows.isSuperResolutionInputFramesEditable).toBe(false)
    expect(rows.effectiveSuperResolutionNumFrames).toBe(5)
    expect(rows.superResolutionFixedWindowRows).toEqual([{ label: '邻帧窗口', value: '5 帧（固定）' }])
    expect(rows.interpolationMetricRows[0].label).toBe('参数量')
    expect(rows.superResolutionMetricRows[2].label).toBe('显存估算')
    expect(rows.combinedVramMetricRows).toEqual([{ label: '组合峰值', value: '0.0 MiB' }])
  })
})
