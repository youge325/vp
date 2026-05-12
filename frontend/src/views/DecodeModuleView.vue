<script setup lang="ts">
import { computed } from 'vue'
import { useDecodeForm } from '@/composables/forms/useDecodeForm'
import { useWorkbenchEditor, useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import BaseField from '@/components/forms/BaseField.vue'
import BaseSelect from '@/components/forms/BaseSelect.vue'

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

const { editorConfig } = useWorkbenchEditor()
const { targetLabel, caption } = useEditingScope('decode')

const decoderProfileOptions = computed(() =>
  visibleDecoderProfiles.value.map((profile) => ({ value: profile.name, label: profile.label })),
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
        <BaseSelect
          label="解码方案"
          :model-value="currentDecoderProfile?.name ?? 'software'"
          :options="decoderProfileOptions"
          @update:model-value="setDecodeProfile"
        />

        <BaseField label="硬件设备">
          <input
            :value="editorConfig.decodeConfig.hwaccelDevice"
            type="text"
            placeholder="留空则使用默认设备"
            @input="setDecodeHwaccelDevice(($event.target as HTMLInputElement).value)"
          />
        </BaseField>
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
