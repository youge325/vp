// pure: no Vue / no Pinia / no Tauri
// Algorithm lookup and backend compatibility helpers for enhance workflow rules.

import type { AlgorithmInfo, EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'

const TENSOR_BACKENDS: TensorBackend[] = ['pytorch', 'paddle', 'onnx']

function isTensorBackend(value: string): value is TensorBackend {
  return TENSOR_BACKENDS.includes(value as TensorBackend)
}

export function algorithmSupportsBackend(
  algorithm: { tensorBackends?: ReadonlyArray<string> } | null | undefined,
  backend: TensorBackend,
): boolean {
  return Boolean(algorithm?.tensorBackends?.includes(backend))
}

export function pickBackendSupportedAlgorithmName(
  algorithms: ReadonlyArray<{ name: string; tensorBackends?: ReadonlyArray<string> }> | null | undefined,
  backend: TensorBackend,
  fallbackName: string,
): string {
  const all = algorithms ?? []
  return all.find((algorithm) => algorithmSupportsBackend(algorithm, backend))?.name ?? all[0]?.name ?? fallbackName
}

export function findInterpolationAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  name: string,
): AlgorithmInfo | undefined {
  return checkResult?.interpolationAlgorithms?.find((algorithm) => algorithm.name === name)
}

export function findSuperResolutionAlgorithm(
  checkResult: EnvironmentCheckResult | null,
  name: string,
): AlgorithmInfo | undefined {
  return checkResult?.superResolutionAlgorithms?.find((algorithm) => algorithm.name === name)
}

export function pickSupportedBackend(
  algorithm: AlgorithmInfo | undefined,
  fallback: TensorBackend,
): TensorBackend {
  if (!algorithm) return fallback
  if (algorithmSupportsBackend(algorithm, fallback)) return fallback
  return algorithm.tensorBackends.find(isTensorBackend) ?? fallback
}
