import { describe, expect, it } from 'vitest'

import { buildEnhanceRuntimeView } from '@/services/preset/enhance-runtime-view'
import { createRuntimeDetails, createRuntimeWorkflow } from '../../fixtures/enhance-runtime'

describe('enhance runtime view', () => {
  it('builds runtime estimates, fixed-window rows, and combined VRAM rows', () => {
    const workflow = createRuntimeWorkflow()
    const {
      fixedWindowAlgorithm,
      interpolationDetail,
      superResolutionDetail,
    } = createRuntimeDetails()

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
