import type { ModelVariantInfo } from '@/types/protocol'
import type { MetricRow, RuntimeMetricEstimate } from '@/types/view/model-metrics'
import { formatBytes, formatGflops, formatParameterCount } from './model-metric-format'

export function metricRows(
  detail: ModelVariantInfo | null | undefined,
  estimate: RuntimeMetricEstimate | null | undefined,
): MetricRow[] {
  return [
    { label: '参数量', value: formatParameterCount(detail?.metrics.parameterCount) },
    { label: '计算量', value: formatGflops(estimate?.gflops) },
    { label: '显存估算', value: formatBytes(estimate?.vramBytes) },
  ]
}

export function combinedVramMetricRows(vramBytes: number | null | undefined): MetricRow[] {
  return [
    { label: '组合峰值', value: formatBytes(vramBytes) },
  ]
}
