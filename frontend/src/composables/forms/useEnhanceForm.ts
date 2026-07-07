// 视图 form-binding — 增强模块(补帧 / 超分 / 动漫优化)。
// 单字段 lens 走 ``field``;含副作用(切换 backend 时联动 onnxModel,
// 切换 algorithm 时重置 model 默认值)的两个 setter 走 ``effect``。

import { computed, reactive } from 'vue'
import { useEnvStore } from '@/stores/env'
import { createDraftEditor } from '@/composables/forms/lens'
import { createAlgorithmLens } from '@/composables/forms/enhance-lens'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import {
  combinedVramMetricRows,
  estimateCombinedPeakVram,
  estimateModelRuntimeMetrics,
  metricRows,
} from '@/services/model-metrics'
import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
  pickDefaultEngine,
  pickDefaultInterpolationAlgorithm,
  pickDefaultInterpolationModel,
  pickDefaultSuperResolutionAlgorithm,
} from '@/services/preset/enhance-rules'
import type { AlgorithmInfo } from '@/types/domain/env'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

const PADDLEGAN_VSR_ALGORITHMS = new Set([
  'ppmsvsr',
  'ppmsvsr-large',
  'edvr',
  'basicvsr',
  'iconvsr',
  'basicvsr-plus-plus',
])

const TENSOR_BACKENDS: TensorBackend[] = ['pytorch', 'paddle', 'onnx']

function isTensorBackend(value: string): value is TensorBackend {
  return TENSOR_BACKENDS.includes(value as TensorBackend)
}

function isPaddleGanVsr(algorithm: AlgorithmInfo | undefined): boolean {
  return Boolean(algorithm && PADDLEGAN_VSR_ALGORITHMS.has(algorithm.name))
}

function fixedRuntimeFrameCount(algorithm: AlgorithmInfo | undefined): number | null {
  if (algorithm?.sequenceMode !== 'window') return null
  const count = algorithm.modelDetails?.[0]?.metrics.runtimeFrameCount ?? algorithm.defaultNumFrames ?? null
  return typeof count === 'number' && Number.isFinite(count) ? Math.max(1, Math.round(count)) : null
}

export function useEnhanceForm() {
  const envStore = useEnvStore()
  const { activeItem, editorConfig, patchWorkflow, patchWorkflowAndPreset } = useWorkbenchEditor()

  const workflow = computed(() => editorConfig.value.workflowConfig)
  const { field, effect } = createDraftEditor<WorkflowConfig>(
    () => workflow.value,
    patchWorkflow,
  )
  const { field: persistentField } = createDraftEditor<WorkflowConfig>(
    () => workflow.value,
    patchWorkflowAndPreset,
  )

  // Phase 8 — 算法下拉列表按当前选中的 tensorBackend 过滤。
  // 没有 ``tensorBackends`` 字段的旧缓存(Phase 8 之前持久化的)
  // 退化为 ``[]``,这里 ``.includes(backend)`` 返回 false,意味着
  // "未声明支持 = 不显示";比错显示安全。
  const interpolationBackendValue = computed(() => workflow.value.interpolation.tensorBackend as TensorBackend)
  const superResolutionBackendValue = computed(() => workflow.value.superResolution.tensorBackend as TensorBackend)

  const interpolation = createAlgorithmLens(
    computed(() => envStore.env.checkResult?.interpolationAlgorithms ?? []),
    computed(() => workflow.value.interpolation.algorithm),
    interpolationBackendValue,
  )

  const superResolutionAlgorithmSpecs = computed(() => envStore.env.checkResult?.superResolutionAlgorithms ?? [])
  const superResolution = createAlgorithmLens(
    superResolutionAlgorithmSpecs,
    computed(() => workflow.value.superResolution.algorithm),
    superResolutionBackendValue,
  )

  const animeProfiles = computed(() => envStore.env.checkResult?.animeProfiles ?? [])
  const isInterpolationOnnxBackend = computed(() => interpolationBackendValue.value === 'onnx')
  const isSuperResolutionOnnxBackend = computed(() => superResolutionBackendValue.value === 'onnx')
  const currentInterpolationAlgorithm = interpolation.current
  const currentSuperResolutionAlgorithm = computed(() =>
    superResolutionAlgorithmSpecs.value.find((a) => a.name === workflow.value.superResolution.algorithm),
  )
  const isPaddleGanSuperResolution = computed(() => isPaddleGanVsr(currentSuperResolutionAlgorithm.value))
  const interpolationModelDetails = computed(() => currentInterpolationAlgorithm.value?.modelDetails ?? [])
  const interpolationOnnxModelDetails = computed(() => currentInterpolationAlgorithm.value?.onnxModelDetails ?? [])
  const superResolutionModelDetails = computed(() => currentSuperResolutionAlgorithm.value?.modelDetails ?? [])
  const superResolutionOnnxModelDetails = computed(() => currentSuperResolutionAlgorithm.value?.onnxModelDetails ?? [])
  const currentInterpolationModelDetail = computed(() => {
    if (isInterpolationOnnxBackend.value) {
      const selected = workflow.value.interpolation.onnxModel ?? ''
      return interpolationOnnxModelDetails.value.find((detail) => detail.name === selected)
    }
    return interpolationModelDetails.value.find((detail) => detail.name === workflow.value.interpolation.model)
  })
  const currentSuperResolutionModelDetail = computed(() => {
    if (isSuperResolutionOnnxBackend.value) {
      const selected = workflow.value.superResolution.onnxModel ?? ''
      return superResolutionOnnxModelDetails.value.find((detail) => detail.name === selected)
    }
    return superResolutionModelDetails.value[0]
  })
  const superResolutionRuntimeFrameCount = computed(() =>
    currentSuperResolutionModelDetail.value?.metrics.runtimeFrameCount ?? null,
  )
  const isSuperResolutionInputFramesEditable = computed(() =>
    isPaddleGanSuperResolution.value && currentSuperResolutionAlgorithm.value?.sequenceMode !== 'window',
  )
  const superResolutionFixedWindowRows = computed(() => {
    if (!isPaddleGanSuperResolution.value || isSuperResolutionInputFramesEditable.value) {
      return []
    }
    const count = fixedRuntimeFrameCount(currentSuperResolutionAlgorithm.value)
    return count ? [{ label: '邻帧窗口', value: `${count} 帧（固定）` }] : []
  })
  const activeVideoDimensions = computed(() => {
    const info = activeItem.value?.info
    if (!info) return null
    return { width: info.width, height: info.height }
  })
  const interpolationInputDimensions = computed(() => {
    const video = activeVideoDimensions.value
    if (!video) return null
    if (
      workflow.value.superResolution.enabled &&
      workflow.value.processOrder === 'super_resolution_then_interpolation'
    ) {
      const scale = workflow.value.superResolution.scaleFactor || 1
      return {
        width: Math.max(1, Math.round(video.width * scale)),
        height: Math.max(1, Math.round(video.height * scale)),
      }
    }
    return video
  })
  const interpolationRuntimeEstimate = computed(() =>
    estimateModelRuntimeMetrics(
      currentInterpolationModelDetail.value,
      interpolationInputDimensions.value,
      {
        scale: workflow.value.interpolation.scale || 1,
        precisionBytes: workflow.value.interpolation.fp16 ? 2 : 4,
        temporalFrames: 1,
      },
    ),
  )
  const superResolutionRuntimeEstimate = computed(() =>
    estimateModelRuntimeMetrics(
      currentSuperResolutionModelDetail.value,
      activeVideoDimensions.value,
      {
        scale: 1,
        precisionBytes: 4,
        temporalFrames: isSuperResolutionInputFramesEditable.value ? workflow.value.superResolution.numFrames ?? 10 : 1,
        runtimeFrameCount: superResolutionRuntimeFrameCount.value,
      },
    ),
  )
  const interpolationMetricRows = computed(() =>
    metricRows(currentInterpolationModelDetail.value, interpolationRuntimeEstimate.value),
  )
  const superResolutionMetricRows = computed(() =>
    metricRows(currentSuperResolutionModelDetail.value, superResolutionRuntimeEstimate.value),
  )
  const combinedPeakVramBytes = computed(() => {
    if (!workflow.value.interpolation.enabled || !workflow.value.superResolution.enabled) {
      return null
    }
    return estimateCombinedPeakVram(interpolationRuntimeEstimate.value, superResolutionRuntimeEstimate.value)
  })
  const combinedVramRows = computed(() =>
    workflow.value.interpolation.enabled && workflow.value.superResolution.enabled
      ? combinedVramMetricRows(combinedPeakVramBytes.value)
      : [],
  )

  function findSuperResolutionAlgorithm(name: string): AlgorithmInfo | undefined {
    return superResolutionAlgorithmSpecs.value.find((a) => a.name === name)
  }

  function pickSupportedBackend(algorithm: AlgorithmInfo | undefined, fallback: TensorBackend): TensorBackend {
    if (!algorithm) return fallback
    if (algorithm.tensorBackends.includes(fallback)) return fallback
    return algorithm.tensorBackends.find(isTensorBackend) ?? fallback
  }

  function applySuperResolutionAlgorithmDefaults(config: WorkflowConfig, algorithm: AlgorithmInfo | undefined): void {
    if (!algorithm) return

    if (isPaddleGanVsr(algorithm)) {
      config.superResolution.tensorBackend = 'paddle'
      config.superResolution.scaleFactor = 4
      config.superResolution.onnxModel = ''
      config.superResolution.numFrames =
        fixedRuntimeFrameCount(algorithm) ?? algorithm.defaultNumFrames ?? config.superResolution.numFrames ?? 10
      return
    }

    if (algorithm.scaleFactors?.length && !algorithm.scaleFactors.includes(config.superResolution.scaleFactor)) {
      config.superResolution.scaleFactor = algorithm.scaleFactors[0] ?? config.superResolution.scaleFactor
    }

    if (config.superResolution.tensorBackend === 'onnx') {
      config.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(
        envStore.env.checkResult,
        config.superResolution.algorithm,
        config.superResolution.onnxModel,
      )
    }
  }

  function preferOnnxInterpolationForPaddleSuperResolution(config: WorkflowConfig): void {
    if (
      !config.interpolation.enabled ||
      !config.superResolution.enabled ||
      config.superResolution.tensorBackend !== 'paddle' ||
      config.interpolation.tensorBackend !== 'pytorch'
    ) {
      return
    }

    const backend: TensorBackend = 'onnx'
    const algorithm = pickDefaultInterpolationAlgorithm(envStore.env.checkResult, backend)
    config.interpolation.tensorBackend = backend
    config.interpolation.engine = pickDefaultEngine(envStore.env.checkResult, backend) ?? config.interpolation.engine
    config.interpolation.algorithm = algorithm
    config.interpolation.model = pickDefaultInterpolationModel(envStore.env.checkResult, algorithm)
    config.interpolation.onnxModel = fallbackInterpolationOnnxModel(
      envStore.env.checkResult,
      algorithm,
      '',
    )
  }

  // ── 纯字段 lens(读写同一处) ────────────────────────────────────────────
  const interpolationEnabled = effect<boolean>(
    () => workflow.value.interpolation.enabled,
    (value) => patchWorkflow((c) => {
      c.interpolation.enabled = value
      preferOnnxInterpolationForPaddleSuperResolution(c)
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
      c.superResolution.enabled = value
      preferOnnxInterpolationForPaddleSuperResolution(c)
    }),
  )
  const superResolutionEngine = field(
    (c) => (c.superResolution.engine as InferenceEngine) ?? 'cuda',
    (c, v: InferenceEngine) => { c.superResolution.engine = v },
  )
  const superResolutionScale = effect<number>(
    () => workflow.value.superResolution.scaleFactor,
    (value) => patchWorkflow((c) => {
      c.superResolution.scaleFactor = isPaddleGanVsr(findSuperResolutionAlgorithm(c.superResolution.algorithm))
        ? 4
        : value
    }),
  )
  const superResolutionOnnxModel = field(
    (c) => c.superResolution.onnxModel ?? '',
    (c, v: string) => { c.superResolution.onnxModel = v },
  )
  const superResolutionNumFrames = effect<number>(
    () => fixedRuntimeFrameCount(currentSuperResolutionAlgorithm.value) ?? workflow.value.superResolution.numFrames ?? 10,
    (value) => patchWorkflow((c) => {
      const algorithm = findSuperResolutionAlgorithm(c.superResolution.algorithm)
      c.superResolution.numFrames = fixedRuntimeFrameCount(algorithm) ?? value
    }),
  )
  const processOrder = persistentField(
    (c) => c.processOrder as ProcessOrder,
    (c, v: ProcessOrder) => { c.processOrder = v },
  )
  const animeEnabled = persistentField(
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

  // ── 复合 setter(切换时联动其他字段) ────────────────────────────────────
  const interpolationBackend = effect<TensorBackend>(
    () => workflow.value.interpolation.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      c.interpolation.tensorBackend = value
      c.interpolation.engine = pickDefaultEngine(envStore.env.checkResult, value) ?? c.interpolation.engine

      // Phase 8 — 切 backend 后,如果当前选中的算法在新 backend 下
      // 没有实现,自动跳到该 backend 第一个可用算法。否则 UI 会出现
      // "下拉里没这个 algorithm,但 workflow.algorithm 还停在它上面"
      // 的不一致 — 用户保存预设后,下次加载就以为算法消失了。
      const interpolationSupportsCurrent = envStore.env.checkResult?.interpolationAlgorithms
        ?.find((a) => a.name === c.interpolation.algorithm)
        ?.tensorBackends?.includes(value) ?? false
      if (!interpolationSupportsCurrent) {
        const next = pickDefaultInterpolationAlgorithm(envStore.env.checkResult, value)
        c.interpolation.algorithm = next
        c.interpolation.model = pickDefaultInterpolationModel(envStore.env.checkResult, next)
      }

      if (value === 'onnx') {
        c.interpolation.onnxModel = fallbackInterpolationOnnxModel(
          envStore.env.checkResult,
          c.interpolation.algorithm,
          c.interpolation.onnxModel,
        )
      }
    }),
  )

  const superResolutionBackend = effect<TensorBackend>(
    () => workflow.value.superResolution.tensorBackend as TensorBackend,
    (value) => patchWorkflow((c) => {
      c.superResolution.tensorBackend = value
      c.superResolution.engine = pickDefaultEngine(envStore.env.checkResult, value) ?? c.superResolution.engine

      const supportsCurrent = findSuperResolutionAlgorithm(c.superResolution.algorithm)
        ?.tensorBackends?.includes(value) ?? false
      if (!supportsCurrent) {
        c.superResolution.algorithm = pickDefaultSuperResolutionAlgorithm(envStore.env.checkResult, value)
      }

      const algorithm = findSuperResolutionAlgorithm(c.superResolution.algorithm)
      applySuperResolutionAlgorithmDefaults(c, algorithm)

      if (value === 'onnx') {
        c.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(
          envStore.env.checkResult,
          c.superResolution.algorithm,
          c.superResolution.onnxModel,
        )
      }

      preferOnnxInterpolationForPaddleSuperResolution(c)
    }),
  )

  const interpolationAlgorithm = effect<string>(
    () => workflow.value.interpolation.algorithm,
    (value) => patchWorkflow((c) => {
      c.interpolation.algorithm = value
      c.interpolation.model = pickDefaultInterpolationModel(envStore.env.checkResult, value)
    }),
  )

  const superResolutionAlgorithm = effect<string>(
    () => workflow.value.superResolution.algorithm,
    (value) => patchWorkflow((c) => {
      c.superResolution.algorithm = value
      const algorithm = findSuperResolutionAlgorithm(value)
      const backend = pickSupportedBackend(algorithm, c.superResolution.tensorBackend as TensorBackend)
      c.superResolution.tensorBackend = backend
      c.superResolution.engine = pickDefaultEngine(envStore.env.checkResult, backend) ?? c.superResolution.engine
      applySuperResolutionAlgorithmDefaults(c, algorithm)
      preferOnnxInterpolationForPaddleSuperResolution(c)
    }),
  )

  return reactive({
    interpolationOnnxModels: interpolation.onnxModels,
    superResolutionOnnxModels: superResolution.onnxModels,
    interpolationAlgorithms: interpolation.algorithms,
    superResolutionAlgorithms: superResolution.algorithms,
    animeProfiles,
    interpolationModels: interpolation.models,
    interpolationModelDetails,
    interpolationOnnxModelDetails,
    superResolutionModelDetails,
    superResolutionOnnxModelDetails,
    currentInterpolationModelDetail,
    currentSuperResolutionModelDetail,
    interpolationRuntimeEstimate,
    superResolutionRuntimeEstimate,
    interpolationMetricRows,
    superResolutionMetricRows,
    combinedPeakVramBytes,
    combinedVramMetricRows: combinedVramRows,
    isSuperResolutionInputFramesEditable,
    superResolutionInputFramesLabel: '每块输入帧数',
    superResolutionInputFramesHint: '每次送入超分模型的连续输入帧数，会影响显存；不是邻帧窗口。',
    superResolutionFixedWindowRows,
    isOnnxBackend: isInterpolationOnnxBackend,
    isInterpolationOnnxBackend,
    isSuperResolutionOnnxBackend,
    isPaddleGanSuperResolution,
    currentSuperResolutionAlgorithm,
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
  })
}
