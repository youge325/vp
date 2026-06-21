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
import CapabilityOptionField from '@/components/forms/CapabilityOptionField.vue'
import type { RateControlMode } from '@/types/domain/workflow'

const {
  visibleEncoderProfiles,
  encoderOptions,
  rateControlOptions,
  rateControlDisabled,
  rateControlModeHint,
  rateControlValueHint,
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
} = useEncodeForm()

const { pickOutputDirectory } = useOutputPicker()
const { editorConfig } = useWorkbenchEditor()
const { targetLabel } = useEditingScope()
const encodeIssue = useOperationIssue('encode')

const containerOptions = computed(() =>
  CONTAINER_OPTIONS.map((value) => ({ value, label: value.toUpperCase() })),
)

const codecOptions = computed(() =>
  visibleEncoderProfiles.value.map((profile) => ({ value: profile.name, label: profile.label })),
)

function handleRateControlModeChange(value: string): void {
  setRateControlMode(value as RateControlMode)
}

async function handlePickOutputDirectory(): Promise<void> {
  // Phase 16 — IO 失败由 useOutputPicker 内部路由到 issueStore('encode'),
  // 模板里的 ``IssueBanner :issue="encodeIssue"`` 自动接收。
  // Phase 17 — 成功路径走 useWorkbenchEditor.patchOutput 双轨:有 active
  // item 写 item.outputConfig.outputDir,无 active item 写 preset.draftPreset。
  // view 不需要再处理返回值,editorConfig 会自动反映新路径。
  await pickOutputDirectory()
}
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码与输出</h2>
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
        </div>
      </div>

      <div class="field-grid field-grid-2">
        <!-- Phase 18 — outputDir 必填。空时 BaseField 显示红色 error 提示,
             input 加 input-error class 显示红边;canStartBatch 已经在 store
             层 disabled 启动按钮,这里只做即时视觉反馈。 -->
        <BaseField
          label="输出目录"
          span-two
          :error="!editorConfig.outputConfig.outputDir?.trim() ? '必填:请选择或填写输出目录' : null"
        >
          <input
            :value="editorConfig.outputConfig.outputDir"
            type="text"
            placeholder="必填:请选择输出目录"
            :class="{ 'input-error': !editorConfig.outputConfig.outputDir?.trim() }"
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
          :options="rateControlOptions"
          :hint="rateControlModeHint"
          :disabled="rateControlDisabled"
          @update:model-value="handleRateControlModeChange"
        />

        <BaseNumber
          label="码率控制值"
          :model-value="Number(editorConfig.encodeConfig.rateControl.value)"
          :min="0"
          :hint="rateControlValueHint"
          :disabled="rateControlDisabled"
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
        </div>
      </div>

      <!-- Phase 7c — 编码器探测出的 capability options 走与 decode 视图相同的
           ``CapabilityOptionField``,boolean/choice/number/string 由组件内部一处
           switch 决定,模板不再重复四分支结构。 -->
      <div class="field-grid field-grid-2">
        <CapabilityOptionField
          v-for="option in encoderOptions"
          :key="option.name"
          :option="option"
          :model-value="getEncodeOption(option)"
          @update:model-value="setEncodeOption(option.name, $event)"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
/* Phase 18 — 输出目录必填时的红边样式。 */
.input-error {
  border-color: var(--danger, #d6433a) !important;
  outline-color: var(--danger, #d6433a);
}
</style>
