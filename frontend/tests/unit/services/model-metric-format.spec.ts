import { describe, expect, it } from 'vitest'

import {
  formatBytes,
  formatGflops,
  formatParameterCount,
  modelOptionLabel,
} from '@/services/model-metric-format'
import type { ModelVariantInfo } from '@/types/domain/env'

function detail(parameterCount: number | null = 5670892): ModelVariantInfo {
  return {
    name: '4.25',
    label: 'RIFE 4.25',
    metrics: {
      parameterCount,
      analysisStatus: 'ok',
      analysisNotes: [],
    },
  }
}

describe('model metric formatting', () => {
  it('formats parameter counts, FLOPs, byte sizes, and option labels compactly', () => {
    expect(formatParameterCount(5670892)).toBe('5.67M')
    expect(formatGflops(38.65536)).toBe('38.7 GFLOPs')
    expect(formatBytes(22683568)).toBe('21.6 MiB')
    expect(modelOptionLabel('4.25', detail())).toBe('4.25 · 5.67M')
    expect(modelOptionLabel('custom.onnx', detail(null))).toBe('custom.onnx')
  })
})
