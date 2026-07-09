import type { ModelVariantInfo } from '@/types/domain/env'

export interface VideoDimensions {
  width: number
  height: number
}

interface RuntimeMetricOptions {
  scale?: number
  precisionBytes?: number
  temporalFrames?: number
  runtimeFrameCount?: number | null
}

export interface RuntimeMetricEstimate {
  effectiveWidth: number
  effectiveHeight: number
  megapixels: number
  gflops: number | null
  vramBytes: number | null
}

function finiteOrNull(value: number | null | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function padToModulo(value: number, modulo: number | null | undefined): number {
  const normalized = Math.max(1, Math.round(value))
  if (!modulo || modulo <= 1) {
    return normalized
  }
  return Math.ceil(normalized / modulo) * modulo
}

export function estimateModelRuntimeMetrics(
  detail: ModelVariantInfo | null | undefined,
  video: VideoDimensions | null | undefined,
  options: RuntimeMetricOptions = {},
): RuntimeMetricEstimate | null {
  if (!detail || !video || video.width <= 0 || video.height <= 0) {
    return null
  }

  const scale = finiteOrNull(options.scale) ?? 1
  const precisionBytes = finiteOrNull(options.precisionBytes) ?? 4
  const temporalFrames = Math.max(
    1,
    Math.round(finiteOrNull(options.runtimeFrameCount) ?? finiteOrNull(options.temporalFrames) ?? 1),
  )
  const scaledWidth = Math.max(1, Math.round(video.width * scale))
  const scaledHeight = Math.max(1, Math.round(video.height * scale))
  const effectiveWidth = padToModulo(scaledWidth, detail.metrics.inputModulo)
  const effectiveHeight = padToModulo(scaledHeight, detail.metrics.inputModulo)
  const megapixels = (effectiveWidth * effectiveHeight) / 1_000_000
  const vramMegapixels = (scaledWidth * scaledHeight) / 1_000_000
  const gflopsPerMegapixel = finiteOrNull(detail.metrics.gflopsPerMegapixel)
  const activationBytesPerMegapixel = finiteOrNull(detail.metrics.activationBytesPerMegapixel)
  const runtimeOverheadBytes = finiteOrNull(detail.metrics.runtimeOverheadBytes)
  const parameterBytes =
    finiteOrNull(detail.metrics.parameterBytes) ??
    (finiteOrNull(detail.metrics.parameterCount) !== null
      ? (finiteOrNull(detail.metrics.parameterCount) as number) * 4
      : null)
  const precisionScale = precisionBytes / 4

  const gflops = gflopsPerMegapixel === null ? null : gflopsPerMegapixel * megapixels
  const hasRuntimeMemoryMetric = activationBytesPerMegapixel !== null || runtimeOverheadBytes !== null
  const vramBytes = !hasRuntimeMemoryMetric
    ? null
    : (runtimeOverheadBytes ?? 0) +
      (parameterBytes ?? 0) * precisionScale +
      (activationBytesPerMegapixel ?? 0) * vramMegapixels * precisionScale * temporalFrames

  return {
    effectiveWidth,
    effectiveHeight,
    megapixels,
    gflops,
    vramBytes,
  }
}

export function estimateCombinedPeakVram(
  first: Pick<RuntimeMetricEstimate, 'vramBytes'> | null | undefined,
  second: Pick<RuntimeMetricEstimate, 'vramBytes'> | null | undefined,
): number | null {
  const values = [finiteOrNull(first?.vramBytes), finiteOrNull(second?.vramBytes)]
    .filter((value): value is number => value !== null)
  return values.length ? Math.max(...values) : null
}
