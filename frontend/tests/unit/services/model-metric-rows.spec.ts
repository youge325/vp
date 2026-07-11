import { describe, expect, it } from 'vitest'

import { combinedVramMetricRows, metricRows } from '@/services/model-metric-rows'
import type { ModelVariantInfo } from '@/types/domain/env'
import type { RuntimeMetricEstimate } from '@/types/view/model-metrics'

const detail: ModelVariantInfo = {
  name: '4.25',
  label: 'RIFE 4.25',
  metrics: {
    parameterCount: 5670892,
    analysisStatus: 'ok',
    analysisNotes: [],
  },
}

const estimate: RuntimeMetricEstimate = {
  effectiveWidth: 640,
  effectiveHeight: 320,
  megapixels: 0.2048,
  gflops: 3.7888,
  vramBytes: 22683568,
}

describe('model metric rows', () => {
  it('builds model and combined VRAM rows using shared formatters', () => {
    expect(metricRows(detail, estimate)).toEqual([
      { label: '参数量', value: '5.67M' },
      { label: '计算量', value: '3.79 GFLOPs' },
      { label: '显存估算', value: '21.6 MiB' },
    ])
    expect(combinedVramMetricRows(22683568)).toEqual([
      { label: '组合峰值', value: '21.6 MiB' },
    ])
  })
})
