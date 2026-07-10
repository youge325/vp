// pure: no Vue / no Pinia / no Tauri
// Workflow mutation rules for the enhance form.

import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { WorkflowConfig } from '@/types/protocol'
import {
  preferOnnxInterpolationForPaddleSuperResolution,
  resolveSuperResolutionNumFrames,
  resolveSuperResolutionScale,
} from './enhance-workflow-selection'

export {
  applyInterpolationAlgorithmSelectionDefaults as applyInterpolationAlgorithmSelection,
  applyInterpolationBackendSelectionDefaults as applyInterpolationBackendSelection,
  applySuperResolutionAlgorithmSelectionDefaults as applySuperResolutionAlgorithmSelection,
  applySuperResolutionBackendSelectionDefaults as applySuperResolutionBackendSelection,
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
