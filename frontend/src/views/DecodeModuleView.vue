<script setup lang="ts">
import { computed } from 'vue'
import { getVisibleDecoderProfiles } from '@/lib/task-mapper'
import { useWorkbenchEditor } from '@/composables/useEditor'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types'

const envStore = useEnvStore()
const presetStore = usePresetStore()
const { editorConfig, editorVideoCodec, editingScopeLabel, isPresetMode } = useWorkbenchEditor()

const visibleDecoderProfiles = computed(() =>
  getVisibleDecoderProfiles(envStore.env.checkResult, editorVideoCodec.value),
)
const currentDecoderProfile = computed(() =>
  visibleDecoderProfiles.value.find((profile) => profile.name === editorConfig.value.decodeConfig.decoder) ?? null,
)

const decoderOptions = computed(() => currentDecoderProfile.value?.options ?? [])
const targetLabel = computed(() => editingScopeLabel.value.targetLabel)
const caption = computed(() =>
  isPresetMode.value
    ? '启动探测完成后即可直接设置解码策略，后续新导入的视频会继承这些默认值。'
    : '当前修改会同步到激活文件与所有已勾选文件，解码器参数来自 FFmpeg 能力探测。',
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
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>解码设置</h2>
          <p class="panel-caption">{{ caption }}</p>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>解码方案</span>
          <select
            :value="currentDecoderProfile?.name ?? 'software'"
            @change="presetStore.setDecodeProfile(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="profile in visibleDecoderProfiles" :key="profile.name" :value="profile.name">
              {{ profile.label }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>硬件设备</span>
          <input
            :value="editorConfig.decodeConfig.hwaccelDevice"
            type="text"
            placeholder="留空则使用默认设备"
            @input="presetStore.setDecodeHwaccelDevice(($event.target as HTMLInputElement).value)"
          />
        </label>
      </div>

      <div class="chip-row">
        <span class="tag">模式: {{ editorConfig.decodeConfig.mode }}</span>
        <span class="tag">hwaccel: {{ editorConfig.decodeConfig.hwaccel || 'software' }}</span>
        <span class="tag">decoder: {{ editorConfig.decodeConfig.decoder || 'software' }}</span>
      </div>

      <div v-if="decoderOptions.length > 0" class="field-grid field-grid-2">
        <label v-for="option in decoderOptions" :key="option.name" class="field">
          <span>{{ option.label }}</span>

          <label v-if="option.type === 'boolean'" class="toggle-chip">
            <input
              :checked="Boolean(presetStore.getOptionValue(option, editorConfig.decodeConfig.options))"
              type="checkbox"
              @change="presetStore.setDecodeOption(option.name, coerceOptionValue(option, $event))"
            />
            <span>启用</span>
          </label>

          <select
            v-else-if="option.type === 'choice'"
            :value="String(presetStore.getOptionValue(option, editorConfig.decodeConfig.options))"
            @change="presetStore.setDecodeOption(option.name, coerceOptionValue(option, $event))"
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
            :value="Number(presetStore.getOptionValue(option, editorConfig.decodeConfig.options))"
            type="number"
            :min="option.min ?? undefined"
            :max="option.max ?? undefined"
            @input="presetStore.setDecodeOption(option.name, coerceOptionValue(option, $event))"
          />

          <input
            v-else
            :value="String(presetStore.getOptionValue(option, editorConfig.decodeConfig.options))"
            type="text"
            @input="presetStore.setDecodeOption(option.name, coerceOptionValue(option, $event))"
          />
        </label>
      </div>
    </section>
  </div>
</template>
