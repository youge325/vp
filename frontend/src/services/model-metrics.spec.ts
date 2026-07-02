import { describe, expect, it } from 'vitest'

import {
  estimateModelRuntimeMetrics,
  formatBytes,
  formatGflops,
  formatParameterCount,
  modelOptionLabel,
} from './model-metrics'
import type { ModelVariantInfo } from '@/types/domain/env'

function detail(overrides: Partial<ModelVariantInfo['metrics']> = {}): ModelVariantInfo {
  return {
    name: '4.25',
    label: 'RIFE 4.25',
    metrics: {
      parameterCount: 5664776,
      parameterBytes: 22659104,
      gflopsPerMegapixel: 18.5,
      activationBytesPerMegapixel: 220_000_000,
      inputModulo: 64,
      analysisStatus: 'ok',
      analysisNotes: [],
      ...overrides,
    },
  }
}

describe('model metric formatting', () => {
  it('formats parameter counts, FLOPs, and byte sizes compactly', () => {
    expect(formatParameterCount(5664776)).toBe('5.66M')
    expect(formatGflops(38.65536)).toBe('38.7 GFLOPs')
    expect(formatBytes(22659104)).toBe('21.6 MiB')
  })

  it('appends compact parameters to model option labels when available', () => {
    expect(modelOptionLabel('4.25', detail())).toBe('4.25 · 5.66M')
    expect(modelOptionLabel('custom.onnx', detail({ parameterCount: null }))).toBe('custom.onnx')
  })
})

describe('estimateModelRuntimeMetrics', () => {
  it('uses padded scaled resolution for current FLOPs and VRAM estimates', () => {
    const estimate = estimateModelRuntimeMetrics(
      detail(),
      { width: 1920, height: 1080 },
      { scale: 1, precisionBytes: 4, temporalFrames: 1 },
    )

    expect(estimate.effectiveWidth).toBe(1920)
    expect(estimate.effectiveHeight).toBe(1088)
    expect(estimate.gflops).toBeCloseTo(38.65, 2)
    expect(estimate.vramBytes).toBeGreaterThan(400_000_000)
  })

  it('keeps unknown ONNX metrics as null without inventing numbers', () => {
    const estimate = estimateModelRuntimeMetrics(
      detail({
        parameterCount: null,
        parameterBytes: null,
        gflopsPerMegapixel: null,
        activationBytesPerMegapixel: null,
        analysisStatus: 'unknown',
        analysisNotes: ['invalid model'],
      }),
      { width: 1280, height: 720 },
      { scale: 1, precisionBytes: 4, temporalFrames: 1 },
    )

    expect(estimate.gflops).toBeNull()
    expect(estimate.vramBytes).toBeNull()
  })
})
