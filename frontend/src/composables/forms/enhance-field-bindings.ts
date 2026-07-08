import type { ComputedRef } from 'vue'
import { createDraftEditor } from '@/composables/forms/lens'
import {
  applyInterpolationAlgorithmSelection,
  applyInterpolationBackendSelection,
  applyInterpolationEnabled,
  applySuperResolutionAlgorithmSelection,
  applySuperResolutionBackendSelection,
  applySuperResolutionEnabled,
  applySuperResolutionNumFrames,
  applySuperResolutionScale,
} from '@/services/preset/enhance-workflow'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

export interface EnhanceFieldBindingParams {
  workflow: ComputedRef<WorkflowConfig>
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  effectiveSuperResolutionNumFrames: ComputedRef<number>
  patchWorkflow: (mutator: (workflow: WorkflowConfig) => void) => void
}

export function createEnhanceFieldBindings({
  workflow,
  checkResult,
  effectiveSuperResolutionNumFrames,
  patchWorkflow,
}: EnhanceFieldBindingParams) {
  const { field, effect } = createDraftEditor<WorkflowConfig>(
    () => workflow.value,
    patchWorkflow,
  )

  const interpolationEnabled = effect<boolean>(
    () => workflow.value.interpolation.enabled,
    (value) => patchWorkflow((c) => {
      applyInterpolationEnabled(c, value, checkResult.value)
    }),
  )
  const interpolationEngine = field(
    (c) => (c.interpolation.engine as InferenceEngine) ?? 'cuda',
    (c, v: InferenceEngine) => { c.interpolation.engine = v },
  )
  const interpolationModel = field(
    (c) => c.interpolation.model,
    (c, v: string) => { c.interpolation.model = v },
  )
  const interpolationOnnxModel = field(
    (c) => c.interpolation.onnxModel ?? '',
    (c, v: string) => { c.interpolation.onnxModel = v },
  )
  const fpsMode = field(
    (c) => c.fpsMode as FpsMode,
    (c, v: FpsMode) => { c.fpsMode = v },
  )
  const targetFps = field(
    (c) => c.interpolation.targetFps,
    (c, v: number) => { c.interpolation.targetFps = v },
  )
  const interpolationMulti = field(
    (c) => c.interpolation.multi,
    (c, v: number) => { c.interpolation.multi = v },
  )
  const interpolationScale = field(
    (c) => c.interpolation.scale,
    (c, v: number) => { c.interpolation.scale = v },
  )
  const interpolationFp16 = field(
    (c) => c.interpolation.fp16,
    (c, v: boolean) => { c.interpolation.fp16 = v },
  )
  const superResolutionEnabled = effect<boolean>(
    () => workflow.value.superResolution.enabled,
    (value) => patchWorkflow((c) => {
      applySuperResolutionEnabled(c, value, checkResult.value)
    }),
  )
  const superResolutionEngine = field(
    (c) => (c.superResolution.engine as InferenceEngine) ?? 'cuda',
    (c, v: InferenceEngine) => { c.superResolution.engine = v },
  )
  const superResolutionScale = effect<number>(
    () => workflow.value.superResolution.scaleFactor,
    (value) => patchWorkflow((c) => {
      applySuperResolutionScale(c, value, checkResult.value)
    }),
  )
  const superResolutionOnnxModel = field(
    (c) => c.superResolution.onnxModel ?? '',
    (c, v: string) => { c.superResolution.onnxModel = v },
  )
  const superResolutionNumFrames = effect<number>(
    () => effectiveSuperResolutionNumFrames.value,
    (value) => patchWorkflow((c) => {
      applySuperResolutionNumFrames(c, value, checkResult.value)
    }),
  )
  const processOrder = field(
    (c) => c.processOrder as ProcessOrder,
    (c, v: ProcessOrder) => { c.processOrder = v },
  )
  const animeEnabled = field(
    (c) => c.anime.enabled,
    (c, v: boolean) => { c.anime.enabled = v },
  )
  const animeProfile = field(
    (c) => c.anime.profile,
    (c, v: string) => { c.anime.profile = v },
  )
  const animeDenoise = field(
    (c) => c.anime.denoise,
    (c, v: number) => { c.anime.denoise = v },
  )
  const animeEdgeBoost = field(
    (c) => c.anime.edgeBoost,
    (c, v: number) => { c.anime.edgeBoost = v },
  )

  const interpolationBackend = effect<TensorBackend>(
    () => workflow.value.interpolation.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      applyInterpolationBackendSelection(c, value, checkResult.value)
    }),
  )
  const superResolutionBackend = effect<TensorBackend>(
    () => workflow.value.superResolution.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      applySuperResolutionBackendSelection(c, value, checkResult.value)
    }),
  )
  const interpolationAlgorithm = effect<string>(
    () => workflow.value.interpolation.algorithm,
    (value) => patchWorkflow((c) => {
      applyInterpolationAlgorithmSelection(c, value, checkResult.value)
    }),
  )
  const superResolutionAlgorithm = effect<string>(
    () => workflow.value.superResolution.algorithm,
    (value) => patchWorkflow((c) => {
      applySuperResolutionAlgorithmSelection(c, value, checkResult.value)
    }),
  )

  return {
    interpolationEnabled,
    interpolationBackend,
    interpolationEngine,
    interpolationAlgorithm,
    interpolationModel,
    interpolationOnnxModel,
    fpsMode,
    targetFps,
    interpolationMulti,
    interpolationScale,
    interpolationFp16,
    superResolutionEnabled,
    superResolutionBackend,
    superResolutionEngine,
    superResolutionScale,
    superResolutionAlgorithm,
    superResolutionOnnxModel,
    superResolutionNumFrames,
    processOrder,
    animeEnabled,
    animeProfile,
    animeDenoise,
    animeEdgeBoost,
  }
}
