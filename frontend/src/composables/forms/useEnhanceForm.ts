import { computed, reactive, type ComputedRef } from 'vue'

import { createEnhanceAlgorithmBindings } from '@/composables/forms/enhance-algorithm-bindings'
import { createEnhanceEffectBindings } from '@/composables/forms/enhance-effect-bindings'
import { createEnhanceScalarFieldBindings } from '@/composables/forms/enhance-scalar-field-bindings'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import {
  buildEnhanceOptions,
  type EnhanceOptions,
} from '@/services/preset/enhance-options'
import { buildEnhanceReadModel } from '@/services/preset/enhance-read-model'
import { toNumberValue } from '@/services/preset/options'
import { useEnvStore } from '@/stores/env'
import type {
  FpsMode,
  InferenceEngine,
  ModelLicenseInfo,
  ProcessOrder,
  TensorBackend,
} from '@/types/protocol'
import type { MetricRow } from '@/types/view/model-metrics'

const SUPER_RESOLUTION_INPUT_FRAMES_LABEL = '每块输入帧数'
const SUPER_RESOLUTION_INPUT_FRAMES_HINT =
  '每次送入超分模型的连续输入帧数，会影响显存；不是邻帧窗口。'

interface EnhanceFormFields {
  interpolationEnabled: boolean
  interpolationBackend: TensorBackend
  interpolationEngine: InferenceEngine
  interpolationAlgorithm: string
  interpolationModel: string
  interpolationOnnxModel: string
  fpsMode: FpsMode
  targetFps: number
  interpolationMulti: number
  interpolationScale: number
  interpolationFp16: boolean
  superResolutionEnabled: boolean
  superResolutionBackend: TensorBackend
  superResolutionEngine: InferenceEngine
  superResolutionAlgorithm: string
  superResolutionScale: number
  superResolutionOnnxModel: string
  superResolutionNumFrames: number
  processOrder: ProcessOrder
  readonly isInterpolationOnnxBackend: boolean
  readonly isSuperResolutionOnnxBackend: boolean
  readonly isSuperResolutionScaleLocked: boolean
  readonly superResolutionModelLicense: ModelLicenseInfo | null
  readonly superResolutionModelLabel: string
  readonly isSuperResolutionInputFramesEditable: boolean
  readonly superResolutionInputFramesLabel: string
  readonly superResolutionInputFramesHint: string
}

interface EnhanceFormActions {
  setInterpolationMulti(value: string): void
  setSuperResolutionScale(value: string): void
}

interface EnhanceFormMetrics {
  interpolationRows: MetricRow[]
  superResolutionRows: MetricRow[]
  superResolutionFixedWindowRows: MetricRow[]
  combinedVramRows: MetricRow[]
}

interface EnhanceFormModel {
  fields: EnhanceFormFields
  options: ComputedRef<EnhanceOptions>
  actions: EnhanceFormActions
  metrics: ComputedRef<EnhanceFormMetrics>
}

/**
 * Enhance screen composition root.
 *
 * Store-backed writable fields, environment-derived options and the pure read
 * model are assembled exactly once here. Views consume this narrow model and
 * never construct sibling form services themselves.
 */
export function useEnhanceForm(): EnhanceFormModel {
  const envStore = useEnvStore()
  const { activeItem, editorConfig, patchWorkflowAndPreset } = useWorkbenchEditor()

  const workflow = computed(() => editorConfig.value.workflowConfig)
  const checkResult = computed(() => envStore.env.checkResult)
  const activeVideoDimensions = computed(() => {
    const info = activeItem.value?.info
    return info ? { width: info.width, height: info.height } : null
  })

  const algorithms = createEnhanceAlgorithmBindings({ workflow, checkResult })
  const readModel = computed(() =>
    buildEnhanceReadModel({
      workflow: workflow.value,
      activeVideoDimensions: activeVideoDimensions.value,
      currentInterpolationAlgorithm: algorithms.currentInterpolationAlgorithm.value,
      currentSuperResolutionAlgorithm: algorithms.currentSuperResolutionAlgorithm.value,
    }),
  )
  const effects = createEnhanceEffectBindings({
    workflow,
    checkResult,
    effectiveSuperResolutionNumFrames: computed(
      () => readModel.value.effectiveSuperResolutionNumFrames,
    ),
    patchWorkflow: patchWorkflowAndPreset,
  })
  const scalars = createEnhanceScalarFieldBindings({
    workflow,
    patchWorkflow: patchWorkflowAndPreset,
  })

  const fields: EnhanceFormFields = reactive({
    interpolationEnabled: effects.interpolationEnabled,
    interpolationBackend: effects.interpolationBackend,
    interpolationEngine: scalars.interpolationEngine,
    interpolationAlgorithm: effects.interpolationAlgorithm,
    interpolationModel: scalars.interpolationModel,
    interpolationOnnxModel: scalars.interpolationOnnxModel,
    fpsMode: scalars.fpsMode,
    targetFps: scalars.targetFps,
    interpolationMulti: scalars.interpolationMulti,
    interpolationScale: scalars.interpolationScale,
    interpolationFp16: scalars.interpolationFp16,
    superResolutionEnabled: effects.superResolutionEnabled,
    superResolutionBackend: effects.superResolutionBackend,
    superResolutionEngine: scalars.superResolutionEngine,
    superResolutionAlgorithm: effects.superResolutionAlgorithm,
    superResolutionScale: effects.superResolutionScale,
    superResolutionOnnxModel: scalars.superResolutionOnnxModel,
    superResolutionNumFrames: effects.superResolutionNumFrames,
    processOrder: scalars.processOrder,
    isInterpolationOnnxBackend: algorithms.isInterpolationOnnxBackend,
    isSuperResolutionOnnxBackend: algorithms.isSuperResolutionOnnxBackend,
    isSuperResolutionScaleLocked: computed(
      () => readModel.value.isSuperResolutionScaleLocked,
    ),
    superResolutionModelLicense: computed(
      () => readModel.value.superResolutionModelLicense,
    ),
    superResolutionModelLabel: computed(
      () => readModel.value.superResolutionModelLabel,
    ),
    isSuperResolutionInputFramesEditable: computed(
      () => readModel.value.isSuperResolutionInputFramesEditable,
    ),
    superResolutionInputFramesLabel: SUPER_RESOLUTION_INPUT_FRAMES_LABEL,
    superResolutionInputFramesHint: SUPER_RESOLUTION_INPUT_FRAMES_HINT,
  })

  const options = computed(() =>
    buildEnhanceOptions({
      checkResult: checkResult.value
        ? { tensorEngines: checkResult.value.tensorEngines }
        : null,
      interpolationBackend: fields.interpolationBackend,
      superResolutionBackend: fields.superResolutionBackend,
      interpolationAlgorithms: algorithms.interpolationAlgorithms.value,
      interpolationModels: algorithms.interpolationModels.value,
      interpolationOnnxModels: algorithms.interpolationOnnxModels.value,
      interpolationModelDetails: readModel.value.interpolationModelDetails,
      interpolationOnnxModelDetails: readModel.value.interpolationOnnxModelDetails,
      superResolutionAlgorithms: algorithms.superResolutionAlgorithms.value,
      currentSuperResolutionAlgorithm: algorithms.currentSuperResolutionAlgorithm.value,
      superResolutionScaleFactor: fields.superResolutionScale,
      superResolutionOnnxModels: algorithms.superResolutionOnnxModels.value,
      superResolutionOnnxModelDetails: readModel.value.superResolutionOnnxModelDetails,
    }),
  )
  const metrics = computed(() => ({
    interpolationRows: readModel.value.interpolationMetricRows,
    superResolutionRows: readModel.value.superResolutionMetricRows,
    superResolutionFixedWindowRows: readModel.value.superResolutionFixedWindowRows,
    combinedVramRows: readModel.value.combinedVramMetricRows,
  }))
  const actions: EnhanceFormActions = {
    setInterpolationMulti(value) {
      fields.interpolationMulti = toNumberValue(value)
    },
    setSuperResolutionScale(value) {
      fields.superResolutionScale = toNumberValue(value)
    },
  }

  return { fields, options, actions, metrics }
}
