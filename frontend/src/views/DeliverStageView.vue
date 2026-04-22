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
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码与输出</h2>
          <p class="panel-caption">选项来源于启动探测结果。CPU、NVENC、QSV 会按当前机器和 FFmpeg 实际支持情况显示。</p>
        </div>

        <div class="panel-actions">
          <button class="ghost-button" :disabled="!store.activeItem" @click="store.pickOutputDirectory()">
            选择输出目录
          </button>
        </div>
      </div>

      <div v-if="encodeOperationIssue" class="info-banner info-banner-danger">
        <strong>输出目录操作失败</strong>
        <p>{{ encodeOperationIssue.message }}</p>
      </div>

      <div v-if="!store.activeItem" class="empty-state">
        <strong>还没有激活文件</strong>
        <p>请先在输入页导入并激活一个文件，编码页会显示该文件当前的编码方案。</p>
      </div>
    </section>

    <section v-if="store.activeItem" class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>输出配置</h2>
          <p class="panel-caption">所有修改会同步到激活文件与所有勾选文件，输出文件名会按“原文件名 + _processed”自动生成。</p>
        </div>
        <span class="panel-badge">作用于 {{ store.selectedIds.length || 1 }} 个文件</span>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field field-span-2">
          <span>输出目录</span>
          <input
            :value="store.activeItem.outputConfig.outputDir"
            type="text"
            placeholder="留空则使用默认输出目录"
            @input="updateOutputDir"
          />
        </label>

        <label class="field">
          <span>容器</span>
          <select :value="store.activeItem.encodeConfig.container" @change="updateContainer">
            <option v-for="container in CONTAINER_OPTIONS" :key="container" :value="container">
              {{ container.toUpperCase() }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>编码器</span>
          <select
            :value="store.activeItem.encodeConfig.codec"
            @change="store.setEncodeProfile(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="profile in store.visibleEncoderProfiles" :key="profile.name" :value="profile.name">
              {{ profile.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>码率控制模式</span>
          <select :value="store.activeItem.encodeConfig.rateControl.mode" @change="updateRateControlMode">
            <option value="crf">CRF</option>
            <option value="cq">CQ</option>
            <option value="qp">QP</option>
            <option value="bitrate">Bitrate</option>
          </select>
        </label>

        <label class="field">
          <span>码率控制值</span>
          <input
            :value="Number(store.activeItem.encodeConfig.rateControl.value)"
            type="number"
            min="0"
            @input="updateRateControlValue"
          />
        </label>

        <label class="field toggle-field">
          <span>保留音频</span>
          <label class="toggle-chip">
            <input :checked="store.activeItem.encodeConfig.keepAudio" type="checkbox" @change="updateKeepAudio" />
            <span>Keep Audio</span>
          </label>
        </label>

        <label class="field toggle-field">
          <span>完成后打开目录</span>
          <label class="toggle-chip">
            <input :checked="store.activeItem.outputConfig.openOnComplete" type="checkbox" @change="updateOpenOnComplete" />
            <span>Open Folder</span>
          </label>
        </label>
      </div>

      <div class="chip-row">
        <span class="tag">Family: {{ store.activeItem.encodeConfig.family }}</span>
        <span class="tag">Codec: {{ store.activeItem.encodeConfig.codec }}</span>
        <span class="tag">Container: {{ store.activeItem.encodeConfig.container.toUpperCase() }}</span>
      </div>
    </section>

    <section v-if="store.activeItem && encoderOptions.length > 0" class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码器参数</h2>
          <p class="panel-caption">这里只展示当前编码器 `ffmpeg -h encoder=` 探测到的参数。</p>
        </div>
      </div>

      <div class="field-grid field-grid-2">
        <label v-for="option in encoderOptions" :key="option.name" class="field">
          <span>{{ option.label }}</span>

          <label v-if="option.type === 'boolean'" class="toggle-chip">
            <input
              :checked="Boolean(store.getOptionValue(option, store.activeItem.encodeConfig.options))"
              type="checkbox"
              @change="store.setEncodeOption(option.name, coerceOptionValue(option, $event))"
            />
            <span>启用</span>
          </label>

          <select
            v-else-if="option.type === 'choice'"
            :value="String(store.getOptionValue(option, store.activeItem.encodeConfig.options))"
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
            :value="Number(store.getOptionValue(option, store.activeItem.encodeConfig.options))"
            type="number"
            :min="option.min ?? undefined"
            :max="option.max ?? undefined"
            @input="store.setEncodeOption(option.name, coerceOptionValue(option, $event))"
          />

          <input
            v-else
            :value="String(store.getOptionValue(option, store.activeItem.encodeConfig.options))"
            type="text"
            @input="store.setEncodeOption(option.name, coerceOptionValue(option, $event))"
          />
        </label>
      </div>
    </section>
  </div>
</template>
