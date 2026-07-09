import { describe, expect, it } from 'vitest'

import {
  combinedVramMetricRows,
  estimateCombinedPeakVram,
  estimateModelRuntimeMetrics,
  formatBytes,
  formatGflops,
  formatParameterCount,
  metricRows,
  modelOptionLabel,
  resolveMetricsForEngine,
  type MetricRow,
  type RuntimeMetricEstimate,
  type RuntimeMetricOptions,
  type VideoDimensions,
} from './model-metrics'
import type { ModelVariantInfo } from '@/types/domain/env'

function detail(overrides: Partial<ModelVariantInfo['metrics']> = {}): ModelVariantInfo {
  return {
    name: '4.25',
    label: 'RIFE 4.25',
    metrics: {
      parameterCount: 5_670_892,
      parameterBytes: 22_683_568,
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

describe('model metrics compatibility barrel', () => {
  it('re-exports formatting, engine, runtime, and row helpers', () => {
    const video: VideoDimensions = { width: 640, height: 288 }
    const options: RuntimeMetricOptions = { precisionBytes: 2 }
    const estimate: RuntimeMetricEstimate | null = estimateModelRuntimeMetrics(detail(), video, options)
    const rows: MetricRow[] = metricRows(detail(), estimate)

    expect(formatParameterCount(5_670_892)).toBe('5.67M')
    expect(formatGflops(38.65536)).toBe('38.7 GFLOPs')
    expect(formatBytes(22_683_568)).toBe('21.6 MiB')
    expect(modelOptionLabel('4.25', detail())).toBe('4.25 · 5.67M')
    expect(resolveMetricsForEngine(detail(), 'cuda')?.metrics.parameterBytes).toBe(22_683_568)
    expect(estimate?.effectiveHeight).toBe(320)
    expect(estimateCombinedPeakVram(estimate, null)).toBe(estimate?.vramBytes)
    expect(rows[0]).toEqual({ label: '参数量', value: '5.67M' })
    expect(combinedVramMetricRows(22_683_568)).toEqual([{ label: '组合峰值', value: '21.6 MiB' }])
  })
})
