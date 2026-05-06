// 视图选择器 — GPU 能力 view-model。
// 重写自旧 useGpuCapabilities,返回响应式 backend / engine 列表,而不是"computed of function"。

import { computed, type ComputedRef } from 'vue'
import { useEnvStore } from '@/stores/env'
import {
  getAvailableEngines,
  getVisibleBackends,
  shouldShowEngineSelector,
} from '@/services/env/gpu-capabilities'
import type { InferenceEngine, TensorBackend } from '@/types/domain/workflow'

export interface GpuCapabilitiesView {
  visibleBackends: ComputedRef<TensorBackend[]>
  availableEngines: ComputedRef<InferenceEngine[]>
  showEngineSelector: ComputedRef<boolean>
}

export function useGpuCapabilities(backendRef: ComputedRef<TensorBackend>): GpuCapabilitiesView {
  const envStore = useEnvStore()

  return {
    visibleBackends: computed(() => getVisibleBackends(envStore.env.checkResult)),
    availableEngines: computed(() => getAvailableEngines(envStore.env.checkResult, backendRef.value)),
    showEngineSelector: computed(() => shouldShowEngineSelector(envStore.env.checkResult, backendRef.value)),
  }
}
