<script setup lang="ts">
import { computed } from 'vue'
import { CONTAINER_OPTIONS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { CapabilityOptionSpec, CapabilityValue, RateControlMode } from '@/types'

const store = useWorkbenchStore()

const encoderOptions = computed(() => store.currentEncoderProfile?.options ?? [])
const encodeOperationIssue = computed(() =>
  store.operationIssue?.scope === 'encode' ? store.operationIssue.error : null,
)
const isPresetMode = computed(() => store.editingScope === 'preset')
const targetLabel = computed(() =>
  isPresetMode.value ? '默认预设（后续导入会继承）' : `作用于 ${store.editingSelectionCount} 个文件`,
)
const caption = computed(() =>
  isPresetMode.value
    ? '编码与输出参数会保存为默认预设，后续导入的新文件会直接继承这些设置。'
    : '当前修改会同步到激活文件与所有已勾选文件，适合批量统一编码策略。',
)

function coerceOptionValue(option: CapabilityOptionSpec, event: Event): CapabilityValue {
  const target = event.target as HTMLInputElement | HTMLSelectElement
  if (option.type === 'boolean') {
    return (target as HTMLInputElement).checked
  }
  if (option.type === 'number') {
    return Number(target.value)
  }
  return target.value
}

function updateContainer(event: Event): void {
  const value = (event.target as HTMLSelectElement).value
  store.patchEncode((config) => {
    config.container = value
  })
}

function updateKeepAudio(event: Event): void {
  const value = (event.target as HTMLInputElement).checked
  store.patchEncode((config) => {
    config.keepAudio = value
  })
}

function updateOpenOnComplete(event: Event): void {
  const value = (event.target as HTMLInputElement).checked
  store.patchOutput((config) => {
    config.openOnComplete = value
  })
}

function updateRateControlMode(event: Event): void {
  store.setEncodeRateControlMode((event.target as HTMLSelectElement).value as RateControlMode)
}

function updateRateControlValue(event: Event): void {
  store.setEncodeRateControlValue(Number((event.target as HTMLInputElement).value))
}

function updateOutputDir(event: Event): void {
  const value = (event.target as HTMLInputElement).value
  store.patchOutput((config) => {
    config.outputDir = value
  })
}

function updateSegmentFrames(event: Event): void {
  const value = Number((event.target as HTMLInputElement).value)
  store.patchOutput((config) => {
    config.segmentFrames = Number.isFinite(value) && value > 0 ? Math.round(value) : 1000
  })
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
          <button class="ghost-button" @click="store.pickOutputDirectory()">选择输出目录</button>
        </div>
      </div>

      <div v-if="encodeOperationIssue" class="info-banner info-banner-danger">
        <strong>输出目录操作失败</strong>
        <p>{{ encodeOperationIssue.message }}</p>
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
            :value="store.editor.outputConfig.outputDir"
            type="text"
            placeholder="留空则使用默认输出目录"
            @input="updateOutputDir"
          />
        </label>

        <label class="field">
          <span>容器</span>
          <select :value="store.editor.encodeConfig.container" @change="updateContainer">
            <option v-for="container in CONTAINER_OPTIONS" :key="container" :value="container">
              {{ container.toUpperCase() }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>分段帧数</span>
          <input
            :value="Number(store.editor.outputConfig.segmentFrames)"
            type="number"
            min="1"
            step="1"
            @input="updateSegmentFrames"
          />
        </label>

        <label class="field">
          <span>编码器</span>
          <select
            :value="store.editor.encodeConfig.codec"
            @change="store.setEncodeProfile(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="profile in store.visibleEncoderProfiles" :key="profile.name" :value="profile.name">
              {{ profile.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>码率控制模式</span>
          <select :value="store.editor.encodeConfig.rateControl.mode" @change="updateRateControlMode">
            <option value="crf">CRF</option>
            <option value="cq">CQ</option>
            <option value="qp">QP</option>
            <option value="bitrate">Bitrate</option>
          </select>
        </label>

        <label class="field">
          <span>码率控制值</span>
          <input
            :value="Number(store.editor.encodeConfig.rateControl.value)"
            type="number"
            min="0"
            @input="updateRateControlValue"
          />
        </label>

        <label class="field toggle-field">
          <span>保留音频</span>
          <label class="toggle-chip">
            <input :checked="store.editor.encodeConfig.keepAudio" type="checkbox" @change="updateKeepAudio" />
            <span>Keep Audio</span>
          </label>
        </label>

        <label class="field toggle-field">
          <span>完成后打开目录</span>
          <label class="toggle-chip">
            <input :checked="store.editor.outputConfig.openOnComplete" type="checkbox" @change="updateOpenOnComplete" />
            <span>Open Folder</span>
          </label>
        </label>
      </div>

      <div class="chip-row">
        <span class="tag">Family: {{ store.editor.encodeConfig.family }}</span>
        <span class="tag">Codec: {{ store.editor.encodeConfig.codec }}</span>
        <span class="tag">Container: {{ store.editor.encodeConfig.container.toUpperCase() }}</span>
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
              :checked="Boolean(store.getOptionValue(option, store.editor.encodeConfig.options))"
              type="checkbox"
              @change="store.setEncodeOption(option.name, coerceOptionValue(option, $event))"
            />
            <span>启用</span>
          </label>

          <select
            v-else-if="option.type === 'choice'"
            :value="String(store.getOptionValue(option, store.editor.encodeConfig.options))"
            @change="store.setEncodeOption(option.name, coerceOptionValue(option, $event))"
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
            :value="Number(store.getOptionValue(option, store.editor.encodeConfig.options))"
            type="number"
            :min="option.min ?? undefined"
            :max="option.max ?? undefined"
            @input="store.setEncodeOption(option.name, coerceOptionValue(option, $event))"
          />

          <input
            v-else
            :value="String(store.getOptionValue(option, store.editor.encodeConfig.options))"
            type="text"
            @input="store.setEncodeOption(option.name, coerceOptionValue(option, $event))"
          />
        </label>
      </div>
    </section>
  </div>
</template>
