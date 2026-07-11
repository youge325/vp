import { describe, expect, it } from 'vitest'

import { resolveMetricsForEngine } from '@/services/model-engine-metrics'
import type { ModelVariantInfo } from '@/types/domain/env'

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

describe('model engine metrics', () => {
  it('uses TensorRT overrides and clears CUDA memory when TensorRT is uncalibrated', () => {
    const calibrated = resolveMetricsForEngine(
      detail({
        engineMetrics: {
          tensorrt: {
            activationBytesPerMegapixel: 260_000_000,
            runtimeOverheadBytes: 42_000_000,
            analysisStatus: 'ok',
            analysisNotes: ['TensorRT calibrated'],
          },
        },
      }),
      'tensorrt',
    )
    const uncalibrated = resolveMetricsForEngine(
      detail({
        engineMetrics: {
          tensorrt: {
            runtimeOverheadBytes: null,
            activationBytesPerMegapixel: null,
            analysisStatus: 'unknown',
            analysisNotes: ['TensorRT memory is not calibrated'],
          },
        },
      }),
      'tensorrt',
    )

    expect(calibrated?.metrics.activationBytesPerMegapixel).toBe(260_000_000)
    expect(calibrated?.metrics.runtimeOverheadBytes).toBe(42_000_000)
    expect(calibrated?.metrics.analysisNotes).toEqual(['TensorRT calibrated'])
    expect(uncalibrated?.metrics.activationBytesPerMegapixel).toBeNull()
    expect(uncalibrated?.metrics.runtimeOverheadBytes).toBeNull()
  })
})
