<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useEnhanceForm } from '@/composables/forms/useEnhanceForm'
import { useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import { useGpuCapabilities } from '@/composables/selectors/useGpuCapabilities'
import { BACKEND_LABELS, ENGINE_LABELS } from '@/config/gpu-labels'
import BaseNumber from '@/components/forms/BaseNumber.vue'
import BaseSelect from '@/components/forms/BaseSelect.vue'
import BaseToggle from '@/components/forms/BaseToggle.vue'
import { modelOptionLabel } from '@/services/model-metrics'
import type { ModelVariantInfo } from '@/types/domain/env'
import type { FpsMode, InferenceEngine, ProcessOrder, TensorBackend } from '@/types/domain/workflow'

const form = useEnhanceForm()
const interpolationCapabilities = useGpuCapabilities(
  toRef(form, 'interpolationBackend')
)
const superResolutionCapabilities = useGpuCapabilities(
  toRef(form, 'superResolutionBackend')
)
const { targetLabel } = useEditingScope()

// Phase 14.2 — 把所有 select 选项一次性 computed 化,模板里只剩 BaseSelect
// + props,跟 Decode/Encode 视觉对齐。原 EnhanceModuleView 里 8+ 个原生
// <select>+<option v-for> 的样板被收敛掉。
//
// 三处 "number-typed" 的 select(``interpolationMulti``/``superResolutionScale``/
// ``interpolationOnnxModel`` 之外的几个倍率)BaseSelect 只接 string value,
// 需要在 ``@update:model-value`` 处做一次 ``Number()`` cast —— 与
// CapabilityOptionField 内部对 choice value 的 ``String(...)`` cast 是镜像关系。

const backendOptions = computed(() =>
  interpolationCapabilities.visibleBackends.value.map((value) => ({ value, label: BACKEND_LABELS[value] })),
)

const interpolationEngineOptions = computed(() =>
  interpolationCapabilities.availableEngines.value.map((value) => ({ value, label: ENGINE_LABELS[value] || value })),
)

const superResolutionEngineOptions = computed(() =>
  superResolutionCapabilities.availableEngines.value.map((value) => ({ value, label: ENGINE_LABELS[value] || value })),
)

const interpolationAlgorithmOptions = computed(() =>
  form.interpolationAlgorithms.map((alg) => ({ value: alg.name, label: alg.name })),
)

const interpolationModelOptions = computed(() =>
  form.interpolationModels.map((model) => ({
    value: model,
    label: modelOptionLabel(model, findDetail(form.interpolationModelDetails, model)),
  })),
)

// ONNX 模型空列表的情况:仍然渲染 select(disabled),options 里只有占位
// "未选择",hint 提示用户去放 .onnx 文件 —— BaseField 自带的 hint slot
// 替换掉原视图末尾的 ``<span class="field-hint">``。
const interpolationOnnxOptions = computed(() => [
  { value: '', label: '未选择' },
  ...form.interpolationOnnxModels.map((model) => ({
    value: model,
    label: modelOptionLabel(model, findDetail(form.interpolationOnnxModelDetails, model)),
  })),
])

const FPS_MODE_OPTIONS = [
  { value: 'target', label: '目标 FPS' },
  { value: 'multi', label: '倍率' },
] as const

const MULTI_OPTIONS = [
  { value: '2', label: '2x' },
  { value: '4', label: '4x' },
] as const

const superResolutionAlgorithmOptions = computed(() =>
  form.superResolutionAlgorithms.map((alg) => ({
    value: alg.name,
    label: modelOptionLabel(alg.name, alg.modelDetails?.[0]),
  })),
)

const superResolutionOnnxOptions = computed(() => [
  { value: '', label: '未选择' },
  ...form.superResolutionOnnxModels.map((model) => ({
    value: model,
    label: modelOptionLabel(model, findDetail(form.superResolutionOnnxModelDetails, model)),
  })),
])

const PROCESS_ORDER_OPTIONS = [
  { value: 'super_resolution_then_interpolation', label: '先超分后补帧' },
  { value: 'frame_interpolation_then_super_resolution', label: '先补帧后超分' },
] as const

const animeProfileOptions = computed(() =>
  form.animeProfiles.map((profile) => ({ value: profile, label: profile })),
)

function findDetail(details: ModelVariantInfo[], name: string): ModelVariantInfo | undefined {
  return details.find((detail) => detail.name === name)
}

function setInterpolationBackend(value: string): void {
  form.interpolationBackend = value as TensorBackend
}

function setInterpolationEngine(value: string): void {
  form.interpolationEngine = value as InferenceEngine
}

function setSuperResolutionBackend(value: string): void {
  form.superResolutionBackend = value as TensorBackend
}

function setSuperResolutionEngine(value: string): void {
  form.superResolutionEngine = value as InferenceEngine
}

function setFpsMode(value: string): void {
  form.fpsMode = value as FpsMode
}

function setInterpolationMulti(value: string): void {
  form.interpolationMulti = Number(value)
}

function setSuperResolutionScale(value: string): void {
  form.superResolutionScale = Number(value)
}

function setProcessOrder(value: string): void {
  form.processOrder = value as ProcessOrder
}
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>增强流程</h2>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <h2>补帧</h2>
        <label class="toggle-chip">
          <input v-model="form.interpolationEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <BaseSelect
          label="后端"
          :model-value="form.interpolationBackend"
          :options="backendOptions"
          @update:model-value="setInterpolationBackend"
        />

        <BaseSelect
          v-if="interpolationCapabilities.showEngineSelector.value"
          label="推理引擎"
          :model-value="form.interpolationEngine"
          :options="interpolationEngineOptions"
          @update:model-value="setInterpolationEngine"
        />

        <BaseSelect
          label="算法"
          :model-value="form.interpolationAlgorithm"
          :options="interpolationAlgorithmOptions"
          @update:model-value="(v) => (form.interpolationAlgorithm = v)"
        />

        <BaseSelect
          v-if="!form.isInterpolationOnnxBackend"
          label="模型"
          :model-value="form.interpolationModel"
          :options="interpolationModelOptions"
          @update:model-value="(v) => (form.interpolationModel = v)"
        />

        <BaseSelect
          v-if="form.isInterpolationOnnxBackend"
          label="ONNX 补帧模型"
          :model-value="form.interpolationOnnxModel"
          :options="interpolationOnnxOptions"
          :disabled="form.interpolationOnnxModels.length === 0"
          :hint="form.interpolationOnnxModels.length === 0
            ? '未找到 ONNX 模型，请将 .onnx 文件放入 models/interpolation 目录'
            : undefined"
          @update:model-value="(v) => (form.interpolationOnnxModel = v)"
        />

        <BaseSelect
          label="帧率模式"
          :model-value="form.fpsMode"
          :options="FPS_MODE_OPTIONS"
          @update:model-value="setFpsMode"
        />

        <BaseNumber
          v-if="form.fpsMode === 'target'"
          label="目标 FPS"
          :model-value="form.targetFps"
          :min="24"
          :max="240"
          @update:model-value="(v) => (form.targetFps = v)"
        />

        <BaseSelect
          v-else
          label="倍率"
          :model-value="String(form.interpolationMulti)"
          :options="MULTI_OPTIONS"
          @update:model-value="setInterpolationMulti"
        />

        <BaseNumber
          label="Scale"
          :model-value="form.interpolationScale"
          :min="0.25"
          :max="1"
          :step="0.05"
          @update:model-value="(v) => (form.interpolationScale = v)"
        />

        <BaseToggle
          label="精度"
          chip-text="FP16"
          :model-value="form.interpolationFp16"
          @update:model-value="(v) => (form.interpolationFp16 = v)"
        />
      </div>

      <div class="model-metric-grid" aria-label="补帧模型指标">
        <div v-for="row in form.interpolationMetricRows" :key="row.label" class="model-metric-item">
          <span>{{ row.label }}</span>
          <strong>{{ row.value }}</strong>
        </div>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <h2>超分</h2>
        <label class="toggle-chip">
          <input v-model="form.superResolutionEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <BaseSelect
          label="后端"
          :model-value="form.superResolutionBackend"
          :options="backendOptions"
          @update:model-value="setSuperResolutionBackend"
        />

        <BaseSelect
          v-if="superResolutionCapabilities.showEngineSelector.value"
          label="推理引擎"
          :model-value="form.superResolutionEngine"
          :options="superResolutionEngineOptions"
          @update:model-value="setSuperResolutionEngine"
        />

        <BaseSelect
          label="算法"
          :model-value="form.superResolutionAlgorithm"
          :options="superResolutionAlgorithmOptions"
          @update:model-value="(v) => (form.superResolutionAlgorithm = v)"
        />

        <BaseSelect
          label="倍率"
          :model-value="String(form.superResolutionScale)"
          :options="MULTI_OPTIONS"
          :disabled="form.isPaddleGanSuperResolution"
          @update:model-value="setSuperResolutionScale"
        />

        <BaseSelect
          v-if="form.isSuperResolutionOnnxBackend"
          label="ONNX 超分模型"
          :model-value="form.superResolutionOnnxModel"
          :options="superResolutionOnnxOptions"
          :disabled="form.superResolutionOnnxModels.length === 0"
          :hint="form.superResolutionOnnxModels.length === 0
            ? '未找到 ONNX 模型，请将 .onnx 文件放入 models/super_resolution 目录'
            : undefined"
          @update:model-value="(v) => (form.superResolutionOnnxModel = v)"
        />

        <BaseNumber
          v-if="form.isPaddleGanSuperResolution"
          label="帧块数"
          :model-value="form.superResolutionNumFrames"
          :min="1"
          :max="100"
          @update:model-value="(v) => (form.superResolutionNumFrames = v)"
        />

        <BaseSelect
          label="处理顺序"
          span-two
          :model-value="form.processOrder"
          :options="PROCESS_ORDER_OPTIONS"
          @update:model-value="setProcessOrder"
        />
      </div>

      <div class="model-metric-grid" aria-label="超分模型指标">
        <div v-for="row in form.superResolutionMetricRows" :key="row.label" class="model-metric-item">
          <span>{{ row.label }}</span>
          <strong>{{ row.value }}</strong>
        </div>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <h2>动漫优化</h2>
        <label class="toggle-chip">
          <input v-model="form.animeEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-3">
        <BaseSelect
          label="预设"
          :model-value="form.animeProfile"
          :options="animeProfileOptions"
          @update:model-value="(v) => (form.animeProfile = v)"
        />

        <BaseNumber
          label="降噪"
          :model-value="form.animeDenoise"
          :min="0"
          :max="100"
          @update:model-value="(v) => (form.animeDenoise = v)"
        />

        <BaseNumber
          label="边缘增强"
          :model-value="form.animeEdgeBoost"
          :min="0"
          :max="100"
          @update:model-value="(v) => (form.animeEdgeBoost = v)"
        />
      </div>
    </section>
  </div>
</template>
