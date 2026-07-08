// pure: no Vue / no Pinia / no Tauri
// Workflow mutation rules for the enhance form.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'
import {
  applyInterpolationAlgorithmSelectionDefaults,
  applyInterpolationBackendSelectionDefaults,
  applySuperResolutionAlgorithmSelectionDefaults,
  applySuperResolutionBackendSelectionDefaults,
  preferOnnxInterpolationForPaddleSuperResolution,
  resolveSuperResolutionNumFrames,
  resolveSuperResolutionScale,
} from './enhance-workflow-selection'

export function applyInterpolationEnabled(
  config: WorkflowConfig,
  value: boolean,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.interpolation.enabled = value
  preferOnnxInterpolationForPaddleSuperResolution(config, checkResult)
}

export function applySuperResolutionEnabled(
  config: WorkflowConfig,
  value: boolean,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.superResolution.enabled = value
  preferOnnxInterpolationForPaddleSuperResolution(config, checkResult)
}

export function applyInterpolationBackendSelection(
  config: WorkflowConfig,
  value: TensorBackend,
  checkResult: EnvironmentCheckResult | null,
): void {
  applyInterpolationBackendSelectionDefaults(config, value, checkResult)
}

export function applySuperResolutionBackendSelection(
  config: WorkflowConfig,
  value: TensorBackend,
  checkResult: EnvironmentCheckResult | null,
): void {
  applySuperResolutionBackendSelectionDefaults(config, value, checkResult)
}

export function applyInterpolationAlgorithmSelection(
  config: WorkflowConfig,
  value: string,
  checkResult: EnvironmentCheckResult | null,
): void {
  applyInterpolationAlgorithmSelectionDefaults(config, value, checkResult)
}

export function applySuperResolutionAlgorithmSelection(
  config: WorkflowConfig,
  value: string,
  checkResult: EnvironmentCheckResult | null,
): void {
  applySuperResolutionAlgorithmSelectionDefaults(config, value, checkResult)
}

export function applySuperResolutionScale(
  config: WorkflowConfig,
  value: number,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.superResolution.scaleFactor = resolveSuperResolutionScale(config, value, checkResult)
}

export function applySuperResolutionNumFrames(
  config: WorkflowConfig,
  value: number,
  checkResult: EnvironmentCheckResult | null,
): void {
  config.superResolution.numFrames = resolveSuperResolutionNumFrames(config, value, checkResult)
}
