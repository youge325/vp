import { describe, expect, it } from 'vitest'

import { buildEnhanceRuntimeEstimates } from './enhance-runtime-estimates'
import { createDefaultWorkflowConfigForEnvironment } from './workflow-defaults'
import type { ModelVariantInfo } from '@/types/domain/env'

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

describe('enhance runtime estimates', () => {
  it('scales interpolation input after super-resolution and combines peak VRAM', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.processOrder = 'super_resolution_then_interpolation'
    workflow.interpolation.enabled = true
    workflow.interpolation.scale = 1
    workflow.interpolation.fp16 = false
    workflow.superResolution.enabled = true
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 10

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
