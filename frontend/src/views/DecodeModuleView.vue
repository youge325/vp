<script setup lang="ts">
import { computed } from 'vue'
import { useDecodeForm } from '@/composables/forms/useDecodeForm'
import { useWorkbenchEditor, useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import BaseField from '@/components/forms/BaseField.vue'
import BaseSelect from '@/components/forms/BaseSelect.vue'
import CapabilityOptionField from '@/components/forms/CapabilityOptionField.vue'

const {
  visibleDecoderProfiles,
  currentDecoderProfile,
  decoderOptions,
  setDecodeProfile,
  setDecodeHwaccelDevice,
  setDecodeOption,
  getDecodeOption,
} = useDecodeForm()

const { editorConfig } = useWorkbenchEditor()
const { targetLabel } = useEditingScope()

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

      <!-- Phase 7c — 单选/数字/字符串/布尔四分支全部委托给 CapabilityOptionField,
           ``option.type`` 一处判定即可。 -->
      <div v-if="decoderOptions.length > 0" class="field-grid field-grid-2">
        <CapabilityOptionField
          v-for="option in decoderOptions"
          :key="option.name"
          :option="option"
          :model-value="getDecodeOption(option)"
          @update:model-value="setDecodeOption(option.name, $event)"
        />
      </div>
    </section>
  </div>
</template>
