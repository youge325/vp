import { describe, expect, it } from 'vitest'

import { buildEnhanceRuntimeFrameState, buildEnhanceRuntimeRows } from '@/services/preset/enhance-runtime-rows'
import type { RuntimeMetricEstimate } from '@/types/view/model-metrics'
import { createRuntimeDetails, createRuntimeWorkflow } from '../../fixtures/enhance-runtime'

const estimate: RuntimeMetricEstimate = {
  effectiveWidth: 10,
  effectiveHeight: 5,
  megapixels: 0.00005,
  gflops: 1.5,
  vramBytes: 256,
}

describe('enhance runtime rows', () => {
  it('builds fixed-window, metric, and combined VRAM rows', () => {
    const workflow = createRuntimeWorkflow()
    const {
      fixedWindowAlgorithm,
      interpolationDetail,
      superResolutionDetail,
    } = createRuntimeDetails()

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
