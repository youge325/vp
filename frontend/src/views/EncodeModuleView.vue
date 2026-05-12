<script setup lang="ts">
import { computed } from 'vue'
import { CONTAINER_OPTIONS } from '@/config/constants'
import { useEncodeForm } from '@/composables/forms/useEncodeForm'
import { useOutputPicker } from '@/composables/app/useOutputPicker'
import { useWorkbenchEditor, useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import { useOperationIssue } from '@/composables/selectors/useOperationIssue'
import IssueBanner from '@/components/IssueBanner.vue'
import BaseField from '@/components/forms/BaseField.vue'
import BaseNumber from '@/components/forms/BaseNumber.vue'
import BaseSelect from '@/components/forms/BaseSelect.vue'
import BaseToggle from '@/components/forms/BaseToggle.vue'
import type { RateControlMode } from '@/types/domain/workflow'

const {
  visibleEncoderProfiles,
  encoderOptions,
  setEncodeProfile,
  setRateControlMode,
  setRateControlValue,
  setEncodeOption,
  getEncodeOption,
  setContainer,
  setKeepAudio,
  setOutputDir,
  setOpenOnComplete,
  setSegmentFrames,
  coerceOptionValue,
} = useEncodeForm()

const { pickOutputDirectory } = useOutputPicker()
const { editorConfig } = useWorkbenchEditor()
const { targetLabel, caption } = useEditingScope('encode')
const encodeIssue = useOperationIssue('encode')

const containerOptions = computed(() =>
  CONTAINER_OPTIONS.map((value) => ({ value, label: value.toUpperCase() })),
)

const codecOptions = computed(() =>
  visibleEncoderProfiles.value.map((profile) => ({ value: profile.name, label: profile.label })),
)

const RATE_CONTROL_OPTIONS = [
  { value: 'crf', label: 'CRF' },
  { value: 'cq', label: 'CQ' },
  { value: 'qp', label: 'QP' },
  { value: 'bitrate', label: 'Bitrate' },
] as const

function handleRateControlModeChange(value: string): void {
  setRateControlMode(value as RateControlMode)
}

async function handlePickOutputDirectory(): Promise<void> {
  await pickOutputDirectory()
}
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码与输出</h2>
          <p class="panel-caption">{{ caption }}</p>
        </div>

        <div class="panel-actions">
          <span class="panel-badge">{{ targetLabel }}</span>
          <button class="ghost-button" @click="handlePickOutputDirectory">选择输出目录</button>
        </div>
      </div>

      <IssueBanner :issue="encodeIssue" title="输出目录操作失败" />
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>输出配置</h2>
          <p class="panel-caption">编码器选项来自环境探测结果，会根据当前机器与 FFmpeg 的实际支持情况动态显示。</p>
        </div>
      </div>

      <div class="field-grid field-grid-2">
        <BaseField label="输出目录" span-two>
          <input
            :value="editorConfig.outputConfig.outputDir"
            type="text"
            placeholder="留空则使用默认输出目录"
            @input="setOutputDir(($event.target as HTMLInputElement).value)"
          />
        </BaseField>

        <BaseSelect
          label="容器"
          :model-value="editorConfig.encodeConfig.container"
          :options="containerOptions"
          @update:model-value="setContainer"
        />

        <BaseNumber
          label="分段帧数"
          :model-value="Number(editorConfig.outputConfig.segmentFrames)"
          :min="1"
          :step="1"
          @update:model-value="setSegmentFrames"
        />

        <BaseSelect
          label="编码器"
          :model-value="editorConfig.encodeConfig.codec"
          :options="codecOptions"
          @update:model-value="setEncodeProfile"
        />

        <BaseSelect
          label="码率控制模式"
          :model-value="editorConfig.encodeConfig.rateControl.mode"
          :options="RATE_CONTROL_OPTIONS"
          @update:model-value="handleRateControlModeChange"
        />

        <BaseNumber
          label="码率控制值"
          :model-value="Number(editorConfig.encodeConfig.rateControl.value)"
          :min="0"
          @update:model-value="setRateControlValue"
        />

        <BaseToggle
          label="保留音频"
          :model-value="editorConfig.encodeConfig.keepAudio"
          chip-text="Keep Audio"
          @update:model-value="setKeepAudio"
        />

        <BaseToggle
          label="完成后打开目录"
          :model-value="editorConfig.outputConfig.openOnComplete"
          chip-text="Open Folder"
          @update:model-value="setOpenOnComplete"
        />
      </div>

      <div class="chip-row">
        <span class="tag">Family: {{ editorConfig.encodeConfig.family }}</span>
        <span class="tag">Codec: {{ editorConfig.encodeConfig.codec }}</span>
        <span class="tag">Container: {{ editorConfig.encodeConfig.container.toUpperCase() }}</span>
      </div>
    </section>

    <section v-if="encoderOptions.length > 0" class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码器参数</h2>
          <p class="panel-caption">这里展示的是当前编码器从 `ffmpeg -h encoder=` 探测到的可调参数。</p>
        </div>
      </div>

      <div class="field-grid field-grid-2">
        <label v-for="option in encoderOptions" :key="option.name" class="field">
          <span>{{ option.label }}</span>

          <label v-if="option.type === 'boolean'" class="toggle-chip">
            <input
              :checked="Boolean(getEncodeOption(option))"
              type="checkbox"
              @change="setEncodeOption(option.name, coerceOptionValue(option, $event))"
            />
            <span>启用</span>
          </label>

          <select
            v-else-if="option.type === 'choice'"
            :value="String(getEncodeOption(option))"
            @change="setEncodeOption(option.name, coerceOptionValue(option, $event))"
          >
            <option
              v-for="choice in option.choices"
              :key="`${option.name}-${choice.value}`"
              :value="String(choice.value)"
            >
              {{ choice.label }}
            </option>
          </select>

          <input
            v-else-if="option.type === 'number'"
            :value="Number(getEncodeOption(option))"
            type="number"
            :min="option.min ?? undefined"
            :max="option.max ?? undefined"
            @input="setEncodeOption(option.name, coerceOptionValue(option, $event))"
          />

          <input
            v-else
            :value="String(getEncodeOption(option))"
            type="text"
            @input="setEncodeOption(option.name, coerceOptionValue(option, $event))"
          />
        </label>
      </div>
    </section>
  </div>
</template>
