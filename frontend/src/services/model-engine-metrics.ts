import type { ModelVariantInfo } from '@/types/protocol'
import type { InferenceEngine } from '@/types/protocol'

export function resolveMetricsForEngine(
  detail: ModelVariantInfo | null | undefined,
  engine: InferenceEngine | string | null | undefined,
): ModelVariantInfo | null {
  if (!detail) return null
  if (engine !== 'tensorrt') return detail

  const override = detail.metrics.engineMetrics?.tensorrt
  const memoryFieldsFromOverride = Boolean(
    override &&
    (Object.prototype.hasOwnProperty.call(override, 'activationBytesPerMegapixel') ||
      Object.prototype.hasOwnProperty.call(override, 'runtimeOverheadBytes')),
  )

  return {
    ...detail,
    metrics: {
      ...detail.metrics,
      gflopsPerMegapixel: override?.gflopsPerMegapixel ?? detail.metrics.gflopsPerMegapixel ?? null,
      activationBytesPerMegapixel: memoryFieldsFromOverride
        ? override?.activationBytesPerMegapixel ?? null
        : null,
      runtimeOverheadBytes: memoryFieldsFromOverride
        ? override?.runtimeOverheadBytes ?? null
        : null,
      runtimeFrameCount: override?.runtimeFrameCount ?? detail.metrics.runtimeFrameCount ?? null,
      inputModulo: override?.inputModulo ?? detail.metrics.inputModulo ?? null,
      analysisStatus: override?.analysisStatus ?? (memoryFieldsFromOverride ? detail.metrics.analysisStatus : 'unknown'),
      analysisNotes: override?.analysisNotes ?? (
        memoryFieldsFromOverride
          ? detail.metrics.analysisNotes
          : ['TensorRT memory metrics are not calibrated for this model.']
      ),
    },
  }
}
