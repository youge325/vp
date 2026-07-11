<script setup lang="ts">
import { reactive } from 'vue'
import { createEnhanceOptionSetters } from '@/composables/forms/enhance-option-setters'
import { createEnhanceOptionState } from '@/composables/forms/enhance-option-state'
import { useEnhanceForm } from '@/composables/forms/useEnhanceForm'
import { useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import BaseNumber from '@/components/forms/BaseNumber.vue'
import BaseSelect from '@/components/forms/BaseSelect.vue'
import BaseToggle from '@/components/forms/BaseToggle.vue'

const form = useEnhanceForm()
const options = reactive({
  ...createEnhanceOptionState(form),
  ...createEnhanceOptionSetters(form),
})
const { targetLabel } = useEditingScope()
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
          :options="options.backendOptions"
          @update:model-value="options.setInterpolationBackend"
        />

        <BaseSelect
          v-if="options.interpolationShowEngineSelector"
          label="推理引擎"
          :model-value="form.interpolationEngine"
          :options="options.interpolationEngineOptions"
          @update:model-value="options.setInterpolationEngine"
        />

        <BaseSelect
          label="算法"
          :model-value="form.interpolationAlgorithm"
          :options="options.interpolationAlgorithmOptions"
          @update:model-value="options.setInterpolationAlgorithm"
        />

        <BaseSelect
          v-if="!form.isInterpolationOnnxBackend"
          label="模型"
          :model-value="form.interpolationModel"
          :options="options.interpolationModelOptions"
          @update:model-value="options.setInterpolationModel"
        />

        <BaseSelect
          v-if="form.isInterpolationOnnxBackend"
          label="ONNX 补帧模型"
          :model-value="form.interpolationOnnxModel"
          :options="options.interpolationOnnxOptions"
          :disabled="options.interpolationOnnxDisabled"
          :hint="options.interpolationOnnxHint"
          @update:model-value="options.setInterpolationOnnxModel"
        />

        <BaseSelect
          label="帧率模式"
          :model-value="form.fpsMode"
          :options="options.fpsModeOptions"
          @update:model-value="options.setFpsMode"
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
          :options="options.multiOptions"
          @update:model-value="options.setInterpolationMulti"
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
          :options="options.backendOptions"
          @update:model-value="options.setSuperResolutionBackend"
        />

        <BaseSelect
          v-if="options.superResolutionShowEngineSelector"
          label="推理引擎"
          :model-value="form.superResolutionEngine"
          :options="options.superResolutionEngineOptions"
          @update:model-value="options.setSuperResolutionEngine"
        />

        <BaseSelect
          label="算法"
          :model-value="form.superResolutionAlgorithm"
          :options="options.superResolutionAlgorithmOptions"
          @update:model-value="options.setSuperResolutionAlgorithm"
        />

        <BaseSelect
          label="倍率"
          :model-value="String(form.superResolutionScale)"
          :options="options.multiOptions"
          :disabled="form.isPaddleGanSuperResolution"
          @update:model-value="options.setSuperResolutionScale"
        />

        <BaseSelect
          v-if="form.isSuperResolutionOnnxBackend"
          label="ONNX 超分模型"
          :model-value="form.superResolutionOnnxModel"
          :options="options.superResolutionOnnxOptions"
          :disabled="options.superResolutionOnnxDisabled"
          :hint="options.superResolutionOnnxHint"
          @update:model-value="options.setSuperResolutionOnnxModel"
        />

        <BaseNumber
          v-if="form.isSuperResolutionInputFramesEditable"
          :label="form.superResolutionInputFramesLabel"
          :model-value="form.superResolutionNumFrames"
          :min="1"
          :max="100"
          :hint="form.superResolutionInputFramesHint"
          @update:model-value="(v) => (form.superResolutionNumFrames = v)"
        />

        <BaseSelect
          label="处理顺序"
          span-two
          :model-value="form.processOrder"
          :options="options.processOrderOptions"
          @update:model-value="options.setProcessOrder"
        />
      </div>

      <div
        v-if="form.superResolutionFixedWindowRows.length"
        class="model-metric-grid model-metric-grid-compact"
        aria-label="超分固定窗口"
      >
        <div v-for="row in form.superResolutionFixedWindowRows" :key="row.label" class="model-metric-item">
          <span>{{ row.label }}</span>
          <strong>{{ row.value }}</strong>
        </div>
      </div>

      <div class="model-metric-grid" aria-label="超分模型指标">
        <div v-for="row in form.superResolutionMetricRows" :key="row.label" class="model-metric-item">
          <span>{{ row.label }}</span>
          <strong>{{ row.value }}</strong>
        </div>
      </div>

      <div
        v-if="form.combinedVramMetricRows.length"
        class="model-metric-grid model-metric-grid-compact"
        aria-label="增强流程组合显存峰值"
      >
        <div v-for="row in form.combinedVramMetricRows" :key="row.label" class="model-metric-item">
          <span>{{ row.label }}</span>
          <strong>{{ row.value }}</strong>
        </div>
      </div>
    </section>

  </div>
</template>
