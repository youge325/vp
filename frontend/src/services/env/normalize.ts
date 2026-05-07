// pure: no Vue / no Pinia / no Tauri
// 环境探测响应归一化 — 兼容 snake_case / camelCase,补全数组默认值。

import type {
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
  GpuAdapter,
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
  }
}

export function normalizeCheckPayload(raw: EnvironmentCheckPayload): EnvironmentCheckPayload {
  return {
    result: normalizeCheckResult(raw.result),
    source: raw.source === 'cache' ? 'cache' : 'probe',
    checkedAt: raw.checkedAt ?? null,
  }
}
