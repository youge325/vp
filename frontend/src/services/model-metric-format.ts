import type { ModelVariantInfo } from '@/types/domain/env'
import { finiteNumberOrNull } from '@/services/finite-number'

const UNKNOWN = '--'

export function formatParameterCount(value: number | null | undefined): string {
  const count = finiteNumberOrNull(value)
  if (count === null) return UNKNOWN
  if (count >= 1_000_000_000) return `${(count / 1_000_000_000).toFixed(2)}B`
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(2)}M`
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}K`
  return `${Math.round(count)}`
}

export function formatGflops(value: number | null | undefined): string {
  const gflops = finiteNumberOrNull(value)
  if (gflops === null) return UNKNOWN
  return `${gflops >= 10 ? gflops.toFixed(1) : gflops.toFixed(2)} GFLOPs`
}

export function formatBytes(value: number | null | undefined): string {
  const bytes = finiteNumberOrNull(value)
  if (bytes === null) return UNKNOWN
  const mib = bytes / 1024 / 1024
  if (mib >= 1024) return `${(mib / 1024).toFixed(2)} GiB`
  return `${mib.toFixed(1)} MiB`
}

export function modelOptionLabel(value: string, detail?: ModelVariantInfo | null): string {
  const parameterLabel = formatParameterCount(detail?.metrics.parameterCount)
  return parameterLabel === UNKNOWN ? value : `${value} · ${parameterLabel}`
}
