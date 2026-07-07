// pure: no Vue / no Pinia / no Tauri
// 环境探测响应归一化 — 兼容 snake_case / camelCase,补全数组默认值。

import type {
  AlgorithmInfo,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
  GpuAdapter,
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
  }
  return {
    ...raw,
    metrics: {
      ...metrics,
      runtimeOverheadBytes: metrics.runtimeOverheadBytes ?? metricRecord.runtime_overhead_bytes ?? null,
      runtimeFrameCount: metrics.runtimeFrameCount ?? metricRecord.runtime_frame_count ?? null,
      analysisStatus: metrics.analysisStatus ?? 'unknown',
      analysisNotes: metrics.analysisNotes ?? [],
    },
  }
}

function normalizeAlgorithmInfo(raw: AlgorithmInfo): AlgorithmInfo {
  const record = raw as AlgorithmInfo & { sequence_mode?: string | null }
  return {
    ...raw,
    tensorBackends: raw.tensorBackends ?? [],
    models: raw.models ?? [],
    onnxModels: raw.onnxModels ?? [],
    modelDetails: (raw.modelDetails ?? []).map(normalizeModelVariant),
    onnxModelDetails: (raw.onnxModelDetails ?? []).map(normalizeModelVariant),
    scaleFactors: raw.scaleFactors ?? [],
    sequenceMode: raw.sequenceMode ?? record.sequence_mode ?? null,
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
