import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { checkEnvironment as invokeCheckEnvironment } from '@/lib/tauri'
import { getVisibleEncoderProfiles, normalizeTaskError } from '@/lib/task-mapper'
import type {
  AppEnv,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
  GpuAdapter,
  OperationIssue,
  OperationIssueScope,
  TaskError,
} from '@/types'

function createInitialEnv(): AppEnv {
  return {
    lastCheckedAt: null,
    lastProbeAt: null,
    checkSource: null,
    isChecking: false,
    isBootstrapping: false,
    checkResult: null,
    issue: null,
  }
}

function normalizeGpuAdapter(adapter: Record<string, unknown>): GpuAdapter {
  return {
    name: String(adapter.name || ''),
    vendor: (adapter.vendor as GpuAdapter['vendor']) ?? 'other',
    deviceType: (adapter.deviceType ?? adapter.device_type ?? 'other') as GpuAdapter['deviceType'],
    adapterCompatibility: String(adapter.adapterCompatibility ?? adapter.adapter_compatibility ?? ''),
    driverVersion: String(adapter.driverVersion ?? adapter.driver_version ?? ''),
  }
}

function normalizeCheckResult(raw: EnvironmentCheckResult): EnvironmentCheckResult {
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
    tensor_backends: {
      ...raw.tensor_backends,
      pytorch: raw.tensor_backends?.pytorch,
      paddle: raw.tensor_backends?.paddle,
      onnx: raw.tensor_backends?.onnx,
    },
    tensor_engines: {
      pytorch: raw.tensor_engines?.pytorch ?? [],
      paddle: raw.tensor_engines?.paddle ?? [],
      onnx: raw.tensor_engines?.onnx ?? [],
    },
    backend_device_support: {
      pytorch: raw.backend_device_support?.pytorch ?? [],
      paddle: raw.backend_device_support?.paddle ?? [],
      onnx: raw.backend_device_support?.onnx ?? [],
    },
    onnx_runtime: {
      ...(raw.onnx_runtime ?? {}),
      providers: raw.onnx_runtime?.providers ?? [],
    },
    onnx_models: {
      interpolation: raw.onnx_models?.interpolation ?? [],
      super_resolution: raw.onnx_models?.super_resolution ?? [],
    },
  }
}

function normalizeCheckPayload(raw: EnvironmentCheckPayload): EnvironmentCheckPayload {
  return {
    result: normalizeCheckResult(raw.result),
    source: raw.source === 'cache' ? 'cache' : 'probe',
    checkedAt: raw.checkedAt ?? null,
  }
}

export const useEnvStore = defineStore('env', () => {
  const env = reactive<AppEnv>(createInitialEnv())
  const operationIssue = ref<OperationIssue | null>(null)

  const visibleEncoderProfiles = computed(() => getVisibleEncoderProfiles(env.checkResult))

  function setOperationIssue(scope: OperationIssueScope, error: TaskError): void {
    operationIssue.value = { scope, error }
  }

  function clearOperationIssue(scope?: OperationIssueScope): void {
    if (!scope || operationIssue.value?.scope === scope) {
      operationIssue.value = null
    }
  }

  async function recheckEnvironment(forceRefresh = true): Promise<void> {
    env.isChecking = true
    env.issue = null
    try {
      const payload = normalizeCheckPayload((await invokeCheckEnvironment(forceRefresh)) as EnvironmentCheckPayload)
      env.checkResult = payload.result
      env.checkSource = payload.source
      env.lastCheckedAt = new Date().toISOString()
      env.lastProbeAt = payload.checkedAt ?? env.lastCheckedAt
    } catch (error) {
      env.issue = normalizeTaskError(error, 'check_failed')
    } finally {
      env.isChecking = false
    }
  }

  return {
    env,
    operationIssue,
    visibleEncoderProfiles,
    setOperationIssue,
    clearOperationIssue,
    recheckEnvironment,
  }
})
