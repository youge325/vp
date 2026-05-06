<script setup lang="ts">
import { computed } from 'vue'
import { useDecodeForm } from '@/composables/forms/useDecodeForm'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'

const {
  visibleDecoderProfiles,
  currentDecoderProfile,
  decoderOptions,
  setDecodeProfile,
  setDecodeHwaccelDevice,
  setDecodeOption,
  getDecodeOption,
  coerceOptionValue,
} = useDecodeForm()

const { editorConfig, editingScopeLabel, isPresetMode } = useWorkbenchEditor()

const targetLabel = computed(() => editingScopeLabel.value.targetLabel)
const caption = computed(() =>
  isPresetMode.value
    ? '启动探测完成后即可直接设置解码策略，后续新导入的视频会继承这些默认值。'
    : '当前修改会同步到激活文件与所有已勾选文件，解码器参数来自 FFmpeg 能力探测。',
)
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
            @change="setDecodeProfile(($event.target as HTMLSelectElement).value)"
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
            @input="setDecodeHwaccelDevice(($event.target as HTMLInputElement).value)"
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
              :checked="Boolean(getDecodeOption(option))"
              type="checkbox"
              @change="setDecodeOption(option.name, coerceOptionValue(option, $event))"
            />
            <span>启用</span>
          </label>

          <select
            v-else-if="option.type === 'choice'"
            :value="String(getDecodeOption(option))"
            @change="setDecodeOption(option.name, coerceOptionValue(option, $event))"
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
            :value="Number(getDecodeOption(option))"
            type="number"
            :min="option.min ?? undefined"
            :max="option.max ?? undefined"
            @input="setDecodeOption(option.name, coerceOptionValue(option, $event))"
          />

          <input
            v-else
            :value="String(getDecodeOption(option))"
            type="text"
            @input="setDecodeOption(option.name, coerceOptionValue(option, $event))"
          />
        </label>
      </div>
    </section>
  </div>
</template>
