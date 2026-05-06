import { computed } from 'vue'
import { getVisibleBackends, getAvailableEngines, shouldShowEngineSelector } from '@/services/gpu'
import type { EnvironmentCheckResult, TensorBackend } from '@/types'

/**
 * 组合 GPU 能力和推理引擎相关的计算属性。
 *
 * 将 EnhanceModuleView 中分散的 GPU 后端筛选、引擎推断逻辑
 * 集中到一个 composable 中，视图只负责渲染。
 */
export function useGpuCapabilities(checkResult: EnvironmentCheckResult | null) {
  const visibleBackends = computed(() => getVisibleBackends(checkResult))

  const availableEngines = computed(() => {
    // 注意：此 computed 需要外部传入当前选中的 backend
    // 返回一个函数，调用方传入 backend 获取引擎列表
    return (backend: TensorBackend) => getAvailableEngines(checkResult, backend)
  })

  const showEngineSelector = computed(() => {
    // 同样返回函数，调用方传入 backend
    return (backend: TensorBackend) => shouldShowEngineSelector(checkResult, backend)
  })

  return {
    visibleBackends,
    availableEngines,
    showEngineSelector,
  }
}
