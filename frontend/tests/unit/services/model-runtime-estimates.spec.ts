import { describe, expect, it } from 'vitest'

import { estimateCombinedPeakVram, estimateModelRuntimeMetrics } from '@/services/model-runtime-estimates'
import { formatBytes } from '@/services/model-metric-format'
import type { ModelVariantInfo } from '@/types/protocol'

function detail(overrides: Partial<ModelVariantInfo['metrics']> = {}): ModelVariantInfo {
  return {
    name: '4.25',
    label: 'RIFE 4.25',
    metrics: {
      parameterCount: 5670892,
      parameterBytes: 22683568,
      gflopsPerMegapixel: 18.5,
      activationBytesPerMegapixel: 694_800_000,
      runtimeOverheadBytes: 38_000_000,
      inputModulo: 64,
      analysisStatus: 'ok',
      analysisNotes: [],
      ...overrides,
    },
  }
}

describe('model runtime estimates', () => {
  it('uses padded scaled resolution, precision, temporal frames, and peak VRAM', () => {
    const estimate = estimateModelRuntimeMetrics(
      detail(),
      { width: 640, height: 288 },
      { scale: 1, precisionBytes: 2, temporalFrames: 1 },
    )
    const windowEstimate = estimateModelRuntimeMetrics(
      detail({
        parameterCount: 20_633_827,
        parameterBytes: 82_535_308,
        activationBytesPerMegapixel: 7_300_784_570,
        runtimeOverheadBytes: 84_074_752,
        runtimeFrameCount: 5,
        inputModulo: 4,
      }),
      { width: 640, height: 288 },
      { scale: 1, precisionBytes: 4, temporalFrames: 10, runtimeFrameCount: 5 },
    )

    expect(estimate.effectiveHeight).toBe(320)
    expect(estimate.gflops).toBeCloseTo(3.79, 2)
    expect(formatBytes(estimate.vramBytes)).toBe('108.1 MiB')
    expect(formatBytes(windowEstimate.vramBytes)).toBe('6.42 GiB')
    expect(estimateCombinedPeakVram(estimate, windowEstimate)).toBe(windowEstimate.vramBytes)
  })
})
