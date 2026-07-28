import { describe, expect, it } from 'vitest'

import { buildEnhanceRuntimeEstimates } from '@/services/preset/enhance-runtime-estimates'
import { createRuntimeDetails, createRuntimeWorkflow } from '../../fixtures/enhance-runtime'

describe('enhance runtime estimates', () => {
  it('scales interpolation input after super-resolution and combines peak VRAM', () => {
    const workflow = createRuntimeWorkflow()
    const { interpolationDetail, superResolutionDetail } = createRuntimeDetails()

    const estimates = buildEnhanceRuntimeEstimates({
      workflow,
      activeVideoDimensions: { width: 10, height: 5 },
      isSuperResolutionInputFramesEditable: false,
      currentInterpolationRuntimeDetail: interpolationDetail,
      currentSuperResolutionRuntimeDetail: superResolutionDetail,
      superResolutionRuntimeFrameCount: 5,
    })

    expect(estimates.interpolationInputDimensions).toEqual({ width: 40, height: 20 })
    expect(estimates.interpolationRuntimeEstimate?.vramBytes).toBeCloseTo(104.8)
    expect(estimates.superResolutionRuntimeEstimate?.vramBytes).toBeCloseTo(208.5)
    expect(estimates.combinedPeakVramBytes).toBeCloseTo(208.5)
  })
})
