// 视图 form-binding — 增强模块(补帧 / 超分 / 动漫优化)。
// 单字段 lens 走 ``field``;含副作用(切换 backend 时联动 onnxModel,
// 切换 algorithm 时重置 model 默认值)的两个 setter 走 ``effect``。

import { computed, reactive } from 'vue'
import { useEnvStore } from '@/stores/env'
import { createDraftEditor } from '@/composables/forms/lens'
import { createAlgorithmLens } from '@/composables/forms/enhance-lens'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import {
  fallbackInterpolationOnnxModel,
  fallbackSuperResolutionOnnxModel,
  pickDefaultEngine,
  pickDefaultInterpolationAlgorithm,
  pickDefaultInterpolationModel,
  pickDefaultSuperResolutionAlgorithm,
} from '@/services/preset/enhance-rules'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'
import type { WorkflowConfig } from '@/types/protocol'

export function useEnhanceForm() {
  const envStore = useEnvStore()
  const { editorConfig, patchWorkflow } = useWorkbenchEditor()

  const workflow = computed(() => editorConfig.value.workflowConfig)
  const { field, effect } = createDraftEditor<WorkflowConfig>(
    () => workflow.value,
    patchWorkflow,
  )

  // Phase 8 — 算法下拉列表按当前选中的 tensorBackend 过滤。
  // 没有 ``tensorBackends`` 字段的旧缓存(Phase 8 之前持久化的)
  // 退化为 ``[]``,这里 ``.includes(backend)`` 返回 false,意味着
  // "未声明支持 = 不显示";比错显示安全。
  const backend = computed(() => workflow.value.interpolation.tensorBackend)

  const interpolation = createAlgorithmLens(
    computed(() => envStore.env.checkResult?.interpolationAlgorithms ?? []),
    computed(() => workflow.value.interpolation.algorithm),
    backend,
  )

  const superResolution = createAlgorithmLens(
    computed(() => envStore.env.checkResult?.superResolutionAlgorithms ?? []),
    computed(() => workflow.value.superResolution.algorithm),
    backend,
  )

  const animeProfiles = computed(() => envStore.env.checkResult?.animeProfiles ?? [])
  const isOnnxBackend = computed(() => backend.value === 'onnx')

  // ── 纯字段 lens(读写同一处) ────────────────────────────────────────────
  const interpolationEnabled = field(
    (c) => c.interpolation.enabled,
    (c, v: boolean) => { c.interpolation.enabled = v },
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
  const superResolutionEnabled = field(
    (c) => c.superResolution.enabled,
    (c, v: boolean) => { c.superResolution.enabled = v },
  )
  const superResolutionScale = field(
    (c) => c.superResolution.scaleFactor,
    (c, v: number) => { c.superResolution.scaleFactor = v },
  )
  const superResolutionAlgorithm = field(
    (c) => c.superResolution.algorithm,
    (c, v: string) => { c.superResolution.algorithm = v },
  )
  const superResolutionOnnxModel = field(
    (c) => c.superResolution.onnxModel ?? '',
    (c, v: string) => { c.superResolution.onnxModel = v },
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

      const superResolutionSupportsCurrent = envStore.env.checkResult?.superResolutionAlgorithms
        ?.find((a) => a.name === c.superResolution.algorithm)
        ?.tensorBackends?.includes(value) ?? false
      if (!superResolutionSupportsCurrent) {
        c.superResolution.algorithm = pickDefaultSuperResolutionAlgorithm(
          envStore.env.checkResult,
          value,
        )
      }

      if (value === 'onnx') {
        c.interpolation.onnxModel = fallbackInterpolationOnnxModel(
          envStore.env.checkResult,
          c.interpolation.algorithm,
          c.interpolation.onnxModel,
        )
        c.superResolution.onnxModel = fallbackSuperResolutionOnnxModel(
          envStore.env.checkResult,
          c.superResolution.algorithm,
          c.superResolution.onnxModel,
        )
      }
    }),
  )

  const interpolationAlgorithm = effect<string>(
    () => workflow.value.interpolation.algorithm,
    (value) => patchWorkflow((c) => {
      c.interpolation.algorithm = value
      c.interpolation.model = pickDefaultInterpolationModel(envStore.env.checkResult, value)
    }),
  )

  return reactive({
    interpolationOnnxModels: interpolation.onnxModels,
    superResolutionOnnxModels: superResolution.onnxModels,
    interpolationAlgorithms: interpolation.algorithms,
    superResolutionAlgorithms: superResolution.algorithms,
    animeProfiles,
    interpolationModels: interpolation.models,
    isOnnxBackend,
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
    superResolutionScale,
    superResolutionAlgorithm,
    superResolutionOnnxModel,
    processOrder,
    animeEnabled,
    animeProfile,
    animeDenoise,
    animeEdgeBoost,
  })
}
