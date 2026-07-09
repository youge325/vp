// 增强模块 lens 工厂 — 消除 interpolation / superResolution 对称逻辑重复。
//
// ``useEnhanceForm`` 中算法下拉、ONNX 模型、模型列表的过滤/查找模式
// 对补帧和超分完全一致,只是数据源不同。这个工厂把共性提取出来,
// 让 caller 只剩一行声明。

import { computed, type ComputedRef } from 'vue'
import { algorithmSupportsBackend } from '@/services/preset/enhance-workflow-lookup'
import type { AlgorithmInfo } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'

type AlgorithmSpec = AlgorithmInfo

interface AlgorithmLens {
  algorithms: ComputedRef<AlgorithmSpec[]>
  current: ComputedRef<AlgorithmSpec | undefined>
  onnxModels: ComputedRef<string[]>
  models: ComputedRef<string[]>
}

export function createAlgorithmLens(
  allAlgorithms: ComputedRef<AlgorithmSpec[]>,
  algorithmName: ComputedRef<string>,
  backend: ComputedRef<TensorBackend>,
): AlgorithmLens {
  const algorithms = computed(() =>
    allAlgorithms.value.filter((a) => algorithmSupportsBackend(a, backend.value)),
  )

  const current = computed(() =>
    algorithms.value.find((a) => a.name === algorithmName.value),
  )

  const onnxModels = computed(() => current.value?.onnxModels ?? [])
  const models = computed(() => current.value?.models ?? [])

  return { algorithms, current, onnxModels, models }
}
