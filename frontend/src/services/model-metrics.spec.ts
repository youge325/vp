import { describe, expect, it } from 'vitest'

import {
  estimateCombinedPeakVram,
  estimateModelRuntimeMetrics,
  formatBytes,
  formatGflops,
  formatParameterCount,
  modelOptionLabel,
  resolveMetricsForEngine,
} from './model-metrics'
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

describe('model metric formatting', () => {
  it('formats parameter counts, FLOPs, and byte sizes compactly', () => {
    expect(formatParameterCount(5670892)).toBe('5.67M')
    expect(formatGflops(38.65536)).toBe('38.7 GFLOPs')
    expect(formatBytes(22683568)).toBe('21.6 MiB')
  })

  it('appends compact parameters to model option labels when available', () => {
    expect(modelOptionLabel('4.25', detail())).toBe('4.25 · 5.67M')
    expect(modelOptionLabel('custom.onnx', detail({ parameterCount: null }))).toBe('custom.onnx')
  })
})

describe('estimateModelRuntimeMetrics', () => {
  it('uses TensorRT engine metrics for memory while keeping theoretical FLOPs', () => {
    const cudaDetail = detail({
      gflopsPerMegapixel: 18.5,
      activationBytesPerMegapixel: 694_800_000,
      runtimeOverheadBytes: 38_000_000,
      engineMetrics: {
        tensorrt: {
          gflopsPerMegapixel: 18.5,
          activationBytesPerMegapixel: 260_000_000,
          runtimeOverheadBytes: 42_000_000,
          analysisStatus: 'ok',
          analysisNotes: ['TensorRT calibrated'],
        },
      },
    } as Partial<ModelVariantInfo['metrics']>)
    const trtDetail = resolveMetricsForEngine(cudaDetail, 'tensorrt')
    const estimate = estimateModelRuntimeMetrics(
      trtDetail,
      { width: 640, height: 288 },
      { scale: 1, precisionBytes: 4, temporalFrames: 1 },
    )

    expect(estimate?.gflops).toBeCloseTo(3.79, 2)
    expect(formatBytes(estimate?.vramBytes)).toBe('107.4 MiB')
  })

  it('does not reuse CUDA activation memory when TensorRT lacks calibration', () => {
    const cudaDetail = detail({
      engineMetrics: {
        tensorrt: {
          runtimeOverheadBytes: null,
          activationBytesPerMegapixel: null,
          analysisStatus: 'unknown',
          analysisNotes: ['TensorRT memory is not calibrated'],
        },
      },
    } as Partial<ModelVariantInfo['metrics']>)

    const trtDetail = resolveMetricsForEngine(cudaDetail, 'tensorrt')
    const estimate = estimateModelRuntimeMetrics(
      trtDetail,
      { width: 640, height: 288 },
      { scale: 1, precisionBytes: 4, temporalFrames: 1 },
    )

    expect(estimate?.gflops).toBeCloseTo(3.79, 2)
    expect(estimate?.vramBytes).toBeNull()
  })

  it('uses padded scaled resolution for current FLOPs and calibrated VRAM estimates', () => {
    const estimate = estimateModelRuntimeMetrics(
      detail(),
      { width: 640, height: 288 },
      { scale: 1, precisionBytes: 4, temporalFrames: 1 },
    )

    expect(estimate.effectiveWidth).toBe(640)
    expect(estimate.effectiveHeight).toBe(320)
    expect(estimate.gflops).toBeCloseTo(3.79, 2)
    expect(formatBytes(estimate.vramBytes)).toBe('180.0 MiB')
  })

  it('keeps runtime overhead unscaled when estimating RIFE fp16 memory', () => {
    const estimate = estimateModelRuntimeMetrics(
      detail(),
      { width: 640, height: 288 },
      { scale: 1, precisionBytes: 2, temporalFrames: 1 },
    )

    expect(formatBytes(estimate.vramBytes)).toBe('108.1 MiB')
  })

  it('estimates PP-MSVSR memory with calibrated per-frame activation cost', () => {
    const estimate = estimateModelRuntimeMetrics(
      detail({
        parameterCount: 1_453_607,
        parameterBytes: 5_814_428,
        activationBytesPerMegapixel: 1_981_031_424,
        runtimeOverheadBytes: 2_391_117_604,
        inputModulo: 4,
      }),
      { width: 640, height: 288 },
      { scale: 1, precisionBytes: 4, temporalFrames: 10 },
    )

    expect(formatBytes(estimate.vramBytes)).toBe('5.63 GiB')
  })

  it('uses a fixed runtime frame count when a window model declares one', () => {
    const estimate = estimateModelRuntimeMetrics(
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

    expect(formatBytes(estimate.vramBytes)).toBe('6.42 GiB')
  })

  it('combines stage estimates by peak instead of summing framework memory', () => {
    expect(estimateCombinedPeakVram({ vramBytes: 2_000 }, { vramBytes: 5_000 })).toBe(5_000)
    expect(estimateCombinedPeakVram({ vramBytes: null }, { vramBytes: 5_000 })).toBe(5_000)
    expect(estimateCombinedPeakVram({ vramBytes: null }, { vramBytes: null })).toBeNull()
  })

  it('keeps unknown ONNX metrics as null without inventing numbers', () => {
    const estimate = estimateModelRuntimeMetrics(
      detail({
        parameterCount: null,
        parameterBytes: null,
        gflopsPerMegapixel: null,
        activationBytesPerMegapixel: null,
        runtimeOverheadBytes: null,
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
