// pure: no Vue / no Pinia / no Tauri
// 环境探测响应归一化 — 兼容 snake_case / camelCase,补全数组默认值。

import type {
  AlgorithmInfo,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
  GpuAdapter,
  ModelEngineMetricInfo,
  ModelVariantInfo,
} from '@/types/domain/env'

export function normalizeGpuAdapter(adapter: Record<string, unknown>): GpuAdapter {
  return {
    name: String(adapter.name || ''),
    vendor: (adapter.vendor as GpuAdapter['vendor']) ?? 'other',
    deviceType: (adapter.deviceType ?? adapter.device_type ?? 'other') as GpuAdapter['deviceType'],
    adapterCompatibility: String(adapter.adapterCompatibility ?? adapter.adapter_compatibility ?? ''),
    driverVersion: String(adapter.driverVersion ?? adapter.driver_version ?? ''),
  }
}

function normalizeModelVariant(raw: ModelVariantInfo): ModelVariantInfo {
  const metrics = raw.metrics ?? {
    analysisStatus: 'unknown',
    analysisNotes: [],
  }
  const metricRecord = metrics as typeof metrics & {
    runtime_overhead_bytes?: number | null
    runtime_frame_count?: number | null
    engine_metrics?: Record<string, ModelEngineMetricInfo>
  }
  return {
    ...raw,
    metrics: {
      ...metrics,
      runtimeOverheadBytes: metrics.runtimeOverheadBytes ?? metricRecord.runtime_overhead_bytes ?? null,
      runtimeFrameCount: metrics.runtimeFrameCount ?? metricRecord.runtime_frame_count ?? null,
      analysisStatus: metrics.analysisStatus ?? 'unknown',
      analysisNotes: metrics.analysisNotes ?? [],
      engineMetrics: normalizeEngineMetrics(metrics.engineMetrics ?? metricRecord.engine_metrics ?? {}),
    },
  }
}

function normalizeEngineMetrics(
  raw: Record<string, ModelEngineMetricInfo> | undefined,
): Record<string, ModelEngineMetricInfo> {
  const normalized: Record<string, ModelEngineMetricInfo> = {}
  for (const [engine, metrics] of Object.entries(raw ?? {})) {
    const record = metrics as ModelEngineMetricInfo & {
      gflops_per_megapixel?: number | null
      activation_bytes_per_megapixel?: number | null
      runtime_overhead_bytes?: number | null
      runtime_frame_count?: number | null
      input_modulo?: number | null
      analysis_status?: string
      analysis_notes?: string[]
    }
    normalized[engine] = {
      ...metrics,
      gflopsPerMegapixel: metrics.gflopsPerMegapixel ?? record.gflops_per_megapixel ?? null,
      activationBytesPerMegapixel:
        metrics.activationBytesPerMegapixel ?? record.activation_bytes_per_megapixel ?? null,
      runtimeOverheadBytes: metrics.runtimeOverheadBytes ?? record.runtime_overhead_bytes ?? null,
      runtimeFrameCount: metrics.runtimeFrameCount ?? record.runtime_frame_count ?? null,
      inputModulo: metrics.inputModulo ?? record.input_modulo ?? null,
      analysisStatus: metrics.analysisStatus ?? record.analysis_status ?? 'unknown',
      analysisNotes: metrics.analysisNotes ?? record.analysis_notes ?? [],
    }
  }
  return normalized
}

function inferAlgorithmFamily(raw: AlgorithmInfo, sequenceMode: string | null): AlgorithmInfo['family'] {
  if (raw.family) return raw.family
  if (raw.name === 'rife') return 'rife'
  const scaleFactors = raw.scaleFactors ?? []
  const isLegacyPaddleGan =
    raw.tensorBackends?.includes('paddle') &&
    (sequenceMode === 'recurrent' || sequenceMode === 'window') &&
    scaleFactors.length === 1 &&
    scaleFactors[0] === 4
  return isLegacyPaddleGan ? 'paddlegan_vsr' : undefined
}

function inferInputFrameMode(raw: AlgorithmInfo, family: AlgorithmInfo['family'], sequenceMode: string | null): string {
  if (raw.inputFrameMode) return raw.inputFrameMode
  if (family !== 'paddlegan_vsr') return 'none'
  return sequenceMode === 'window' ? 'fixed_window' : 'editable_chunk'
}

function inferFixedScaleFactor(raw: AlgorithmInfo, family: AlgorithmInfo['family']): number | null {
  if (typeof raw.fixedScaleFactor === 'number') return raw.fixedScaleFactor
  const record = raw as AlgorithmInfo & { fixed_scale_factor?: number | null }
  if (typeof record.fixed_scale_factor === 'number') return record.fixed_scale_factor
  const scaleFactors = raw.scaleFactors ?? []
  return family === 'paddlegan_vsr' && scaleFactors.length === 1 ? scaleFactors[0] ?? null : null
}

function normalizeAlgorithmInfo(raw: AlgorithmInfo): AlgorithmInfo {
  const record = raw as AlgorithmInfo & {
    sequence_mode?: string | null
    input_frame_mode?: string | null
    fixed_scale_factor?: number | null
  }
  const sequenceMode = raw.sequenceMode ?? record.sequence_mode ?? null
  const family = inferAlgorithmFamily(raw, sequenceMode)
  return {
    ...raw,
    family,
    tensorBackends: raw.tensorBackends ?? [],
    models: raw.models ?? [],
    onnxModels: raw.onnxModels ?? [],
    modelDetails: (raw.modelDetails ?? []).map(normalizeModelVariant),
    onnxModelDetails: (raw.onnxModelDetails ?? []).map(normalizeModelVariant),
    scaleFactors: raw.scaleFactors ?? [],
    fixedScaleFactor: inferFixedScaleFactor(raw, family),
    sequenceMode,
    inputFrameMode: raw.inputFrameMode ?? record.input_frame_mode ?? inferInputFrameMode(raw, family, sequenceMode),
  }
}

export function normalizeCheckResult(raw: EnvironmentCheckResult): EnvironmentCheckResult {
  const adapters = Array.isArray(raw.gpu?.adapters)
    ? raw.gpu.adapters.map((adapter) => normalizeGpuAdapter(adapter as unknown as Record<string, unknown>))
    : []

  return {
    ...raw,
    ffmpeg: {
      ...raw.ffmpeg,
      hwaccels: raw.ffmpeg?.hwaccels ?? [],
      encoderProfiles: raw.ffmpeg?.encoderProfiles ?? [],
      decoderProfiles: raw.ffmpeg?.decoderProfiles ?? [],
    },
    gpu: {
      ...raw.gpu,
      devices: raw.gpu?.devices ?? [],
      adapters,
    },
    tensorBackends: {
      ...raw.tensorBackends,
      pytorch: raw.tensorBackends?.pytorch,
      paddle: raw.tensorBackends?.paddle,
      onnx: raw.tensorBackends?.onnx,
    },
    tensorEngines: {
      pytorch: raw.tensorEngines?.pytorch ?? [],
      paddle: raw.tensorEngines?.paddle ?? [],
      onnx: raw.tensorEngines?.onnx ?? [],
    },
    backendDeviceSupport: {
      pytorch: raw.backendDeviceSupport?.pytorch ?? [],
      paddle: raw.backendDeviceSupport?.paddle ?? [],
      onnx: raw.backendDeviceSupport?.onnx ?? [],
    },
    onnxRuntime: {
      ...(raw.onnxRuntime ?? {}),
      providers: raw.onnxRuntime?.providers ?? [],
    },
    interpolationAlgorithms: (raw.interpolationAlgorithms ?? []).map(normalizeAlgorithmInfo),
    superResolutionAlgorithms: (raw.superResolutionAlgorithms ?? []).map(normalizeAlgorithmInfo),
  }
}

export function normalizeCheckPayload(raw: EnvironmentCheckPayload): EnvironmentCheckPayload {
  return {
    result: normalizeCheckResult(raw.result),
    source: raw.source === 'cache' ? 'cache' : 'probe',
    checkedAt: raw.checkedAt ?? null,
  }
}
