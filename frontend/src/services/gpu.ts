/** GPU / tensor-backend 纯函数业务逻辑。
 *
 * 不引用任何 Store，只接收原始数据并返回计算结果。
 */

import type { EnvironmentCheckResult, TensorBackend, InferenceEngine } from '@/types'

const ALL_BACKENDS: TensorBackend[] = ['pytorch', 'paddle', 'onnx']

/**
 * 根据 GPU vendor 和环境探测结果，过滤出当前机器可用的 tensor backend 列表。
 */
export function getVisibleBackends(
  checkResult: EnvironmentCheckResult | null,
): TensorBackend[] {
  const vendor = checkResult?.gpu?.adapters?.[0]?.vendor
  const support = checkResult?.backendDeviceSupport

  if (!vendor || vendor === 'other' || !support) {
    return [...ALL_BACKENDS]
  }

  const filtered = ALL_BACKENDS.filter((b) => {
    const supported = support[b]
    return supported && supported.length > 0 ? supported.includes(vendor) : true
  })

  if (filtered.length > 0) {
    return filtered
  }

  // 后备推断：数据异常时根据 vendor 硬编码兼容矩阵
  if (vendor === 'hygon') {
    return ['paddle']
  }

  return [...ALL_BACKENDS]
}

/**
 * 推断当前机器的 GPU vendor（综合 vendor 标签、CUDA 可用性、设备名称）。
 */
export function inferGpuVendor(checkResult: EnvironmentCheckResult | null): 'nvidia' | 'intel' | 'amd' | 'hygon' | 'other' {
  const vendor = checkResult?.gpu?.adapters?.[0]?.vendor
  if (vendor && vendor !== 'other') {
    return vendor
  }

  const cudaAvailable = checkResult?.gpu?.cudaAvailable
  const gpuAvailable = checkResult?.gpu?.available
  const deviceNames = checkResult?.gpu?.devices ?? []
  const hasNvidiaInName = deviceNames.some((name) => name.toLowerCase().includes('nvidia'))

  if (cudaAvailable || hasNvidiaInName || (gpuAvailable === true && vendor === undefined)) {
    return 'nvidia'
  }

  return 'other'
}

/**
 * 获取指定 backend 在当前环境下可用的推理引擎列表。
 */
export function getAvailableEngines(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): InferenceEngine[] {
  const engines = checkResult?.tensorEngines?.[backend] ?? []
  if (engines.length > 0) {
    return engines as InferenceEngine[]
  }

  // 后备推断：后端未返回 tensorEngines 时根据 GPU 信息推断
  const vendor = checkResult?.gpu?.adapters?.[0]?.vendor
  const cudaAvailable = checkResult?.gpu?.cudaAvailable
  const gpuAvailable = checkResult?.gpu?.available
  const deviceNames = checkResult?.gpu?.devices ?? []
  const hasNvidiaInName = deviceNames.some((name) => name.toLowerCase().includes('nvidia'))
  const isNvidia = vendor === 'nvidia' || cudaAvailable || hasNvidiaInName || (gpuAvailable === true && vendor === undefined)

  if (isNvidia) {
    if (backend === 'pytorch') return ['cuda', 'tensorrt']
    if (backend === 'paddle') return ['cuda', 'tensorrt']
    if (backend === 'onnx') return ['tensorrt', 'cuda']
  }

  if (vendor === 'hygon' && backend === 'paddle') return ['dcu']
  if (vendor === 'hygon') return []

  return ['cuda']
}

/**
 * 判断当前是否应显示引擎选择器（有 GPU 且当前后端有可用引擎）。
 */
export function shouldShowEngineSelector(
  checkResult: EnvironmentCheckResult | null,
  backend: TensorBackend,
): boolean {
  const gpuAvailable = checkResult?.gpu?.available
  return gpuAvailable === true && getAvailableEngines(checkResult, backend).length > 0
}

/**
 * 后端设备兼容性矩阵（静态常量）。
 */
export function getBackendDeviceSupport(): Record<TensorBackend, string[]> {
  return {
    pytorch: ['nvidia', 'intel', 'amd'],
    paddle: ['nvidia', 'intel', 'amd', 'hygon'],
    onnx: ['nvidia', 'intel', 'amd'],
  }
}
