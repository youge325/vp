// 视图选择器 — GPU 能力 view-model。
// 重写自旧 useGpuCapabilities,返回响应式 backend / engine 列表,而不是"computed of function"。

import { computed, type Ref } from 'vue'
import { useEnvStore } from '@/stores/env'
import {
  getAvailableEngines,
  getVisibleBackends,
  shouldShowEngineSelector,
} from '@/services/env/gpu-capabilities'
import type { InferenceEngine, TensorBackend } from '@/types/protocol'

interface GpuCapabilitiesView {
  visibleBackends: Ref<TensorBackend[]>
  availableEngines: Ref<InferenceEngine[]>
  showEngineSelector: Ref<boolean>
}

export function useGpuCapabilities(backendRef: Ref<TensorBackend>): GpuCapabilitiesView {
  const envStore = useEnvStore()

  return {
    visibleBackends: computed(() => getVisibleBackends(envStore.env.checkResult)),
    availableEngines: computed(() => getAvailableEngines(envStore.env.checkResult, backendRef.value)),
    showEngineSelector: computed(() => shouldShowEngineSelector(envStore.env.checkResult, backendRef.value)),
  }
}
