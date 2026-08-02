<script setup lang="ts">
import { useEnhanceForm } from '@/composables/forms/useEnhanceForm'
import { useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import BaseNumber from '@/components/forms/BaseNumber.vue'
import BaseSelect from '@/components/forms/BaseSelect.vue'
import BaseToggle from '@/components/forms/BaseToggle.vue'
import ModelMetricGrid from '@/components/ModelMetricGrid.vue'

const { fields, options, actions, metrics } = useEnhanceForm()
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
          <input v-model="fields.interpolationEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <BaseSelect
          v-model="fields.interpolationBackend"
          label="后端"
          :options="options.backendOptions"
        />

        <BaseSelect
          v-if="options.interpolationShowEngineSelector"
          v-model="fields.interpolationEngine"
          label="推理引擎"
          :options="options.interpolationEngineOptions"
        />

        <BaseSelect
          v-model="fields.interpolationAlgorithm"
          label="算法"
          :options="options.interpolationAlgorithmOptions"
        />

        <BaseSelect
          v-if="!fields.isInterpolationOnnxBackend"
          v-model="fields.interpolationModel"
          label="模型"
          :options="options.interpolationModelOptions"
        />

        <BaseSelect
          v-if="fields.isInterpolationOnnxBackend"
          v-model="fields.interpolationOnnxModel"
          label="ONNX 补帧模型"
          :options="options.interpolationOnnxOptions"
          :disabled="options.interpolationOnnxDisabled"
          :hint="options.interpolationOnnxHint"
        />

        <BaseSelect
          v-model="fields.fpsMode"
          label="帧率模式"
          :options="options.fpsModeOptions"
        />

        <BaseNumber
          v-if="fields.fpsMode === 'target'"
          label="目标 FPS"
          :model-value="fields.targetFps"
          :min="24"
          :max="240"
          @update:model-value="(v) => (fields.targetFps = v)"
        />

        <BaseSelect
          v-else
          label="倍率"
          :model-value="String(fields.interpolationMulti)"
          :options="options.multiOptions"
          @update:model-value="actions.setInterpolationMulti"
        />

        <BaseNumber
          label="Scale"
          :model-value="fields.interpolationScale"
          :min="0.25"
          :max="1"
          :step="0.05"
          @update:model-value="(v) => (fields.interpolationScale = v)"
        />

        <BaseToggle
          label="精度"
          chip-text="FP16"
          :model-value="fields.interpolationFp16"
          @update:model-value="(v) => (fields.interpolationFp16 = v)"
        />
      </div>

      <ModelMetricGrid label="补帧模型指标" :rows="metrics.interpolationRows" />
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <h2>超分</h2>
        <label class="toggle-chip">
          <input v-model="fields.superResolutionEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <BaseSelect
          v-model="fields.superResolutionBackend"
          label="后端"
          :options="options.backendOptions"
        />

        <BaseSelect
          v-if="options.superResolutionShowEngineSelector"
          v-model="fields.superResolutionEngine"
          label="推理引擎"
          :options="options.superResolutionEngineOptions"
        />

        <BaseSelect
          v-model="fields.superResolutionAlgorithm"
          label="算法"
          :options="options.superResolutionAlgorithmOptions"
        />

        <BaseSelect
          label="倍率"
          :model-value="String(fields.superResolutionScale)"
          :options="options.superResolutionScaleOptions"
          :disabled="fields.isSuperResolutionScaleLocked"
          @update:model-value="actions.setSuperResolutionScale"
        />

        <BaseSelect
          v-if="fields.isSuperResolutionOnnxBackend"
          v-model="fields.superResolutionOnnxModel"
          label="ONNX 超分模型"
          :options="options.superResolutionOnnxOptions"
          :disabled="options.superResolutionOnnxDisabled"
          :hint="options.superResolutionOnnxHint"
        />

        <BaseNumber
          v-if="fields.isSuperResolutionInputFramesEditable"
          :label="fields.superResolutionInputFramesLabel"
          :model-value="fields.superResolutionNumFrames"
          :min="1"
          :max="100"
          :hint="fields.superResolutionInputFramesHint"
          @update:model-value="(v) => (fields.superResolutionNumFrames = v)"
        />

        <BaseSelect
          v-model="fields.processOrder"
          label="处理顺序"
          span-two
          :options="options.processOrderOptions"
        />
      </div>

      <div
        v-if="fields.superResolutionModelLicense?.usage === 'non_commercial'"
        class="model-license-banner"
        role="note"
      >
        <strong>非商业模型</strong>
        <span>Real-RawVSR BasicVSR 仅限非商业研究与个人使用（{{ fields.superResolutionModelLicense.spdxId }}）。</span>
        <a
          :href="fields.superResolutionModelLicense.sourceUrl"
          target="_blank"
          rel="noreferrer"
        >查看上游说明</a>
      </div>

      <ModelMetricGrid
        label="超分固定窗口"
        :rows="metrics.superResolutionFixedWindowRows"
        compact
      />
      <ModelMetricGrid label="超分模型指标" :rows="metrics.superResolutionRows" />
      <ModelMetricGrid
        label="增强流程组合显存峰值"
        :rows="metrics.combinedVramRows"
        compact
      />
    </section>

  </div>
</template>
