<script setup lang="ts">
import { CONTAINER_OPTIONS } from '@/services/preset/constants'
import { useEncodeForm } from '@/composables/forms/useEncodeForm'
import { useOutputPicker } from '@/composables/app/useOutputPicker'
import { useWorkbenchEditor, useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import { useEnvIssue } from '@/composables/selectors/useEnvIssue'

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
const encodeIssue = useEnvIssue('encode')

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

      <div v-if="encodeIssue" class="info-banner info-banner-danger">
        <strong>输出目录操作失败</strong>
        <p>{{ encodeIssue.message }}</p>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>输出配置</h2>
          <p class="panel-caption">编码器选项来自环境探测结果，会根据当前机器与 FFmpeg 的实际支持情况动态显示。</p>
        </div>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field field-span-2">
          <span>输出目录</span>
          <input
            :value="editorConfig.outputConfig.outputDir"
            type="text"
            placeholder="留空则使用默认输出目录"
            @input="setOutputDir(($event.target as HTMLInputElement).value)"
          />
        </label>

        <label class="field">
          <span>容器</span>
          <select :value="editorConfig.encodeConfig.container" @change="setContainer(($event.target as HTMLSelectElement).value)">
            <option v-for="container in CONTAINER_OPTIONS" :key="container" :value="container">
              {{ container.toUpperCase() }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>分段帧数</span>
          <input
            :value="Number(editorConfig.outputConfig.segmentFrames)"
            type="number"
            min="1"
            step="1"
            @input="setSegmentFrames(Number(($event.target as HTMLInputElement).value))"
          />
        </label>

        <label class="field">
          <span>编码器</span>
          <select
            :value="editorConfig.encodeConfig.codec"
            @change="setEncodeProfile(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="profile in visibleEncoderProfiles" :key="profile.name" :value="profile.name">
              {{ profile.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>码率控制模式</span>
          <select :value="editorConfig.encodeConfig.rateControl.mode" @change="setRateControlMode(($event.target as HTMLSelectElement).value)">
            <option value="crf">CRF</option>
            <option value="cq">CQ</option>
            <option value="qp">QP</option>
            <option value="bitrate">Bitrate</option>
          </select>
        </label>

        <label class="field">
          <span>码率控制值</span>
          <input
            :value="Number(editorConfig.encodeConfig.rateControl.value)"
            type="number"
            min="0"
            @input="setRateControlValue(Number(($event.target as HTMLInputElement).value))"
          />
        </label>

        <label class="field toggle-field">
          <span>保留音频</span>
          <label class="toggle-chip">
            <input :checked="editorConfig.encodeConfig.keepAudio" type="checkbox" @change="setKeepAudio(($event.target as HTMLInputElement).checked)" />
            <span>Keep Audio</span>
          </label>
        </label>

        <label class="field toggle-field">
          <span>完成后打开目录</span>
          <label class="toggle-chip">
            <input :checked="editorConfig.outputConfig.openOnComplete" type="checkbox" @change="setOpenOnComplete(($event.target as HTMLInputElement).checked)" />
            <span>Open Folder</span>
          </label>
        </label>
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
