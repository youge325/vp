<script setup lang="ts">
import type { FilterStep } from '@/types/protocol'

const props = defineProps<{
  modelValue: FilterStep
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: FilterStep): void
}>()

function patch(mutator: (params: Record<string, unknown>) => void) {
  const next: FilterStep = { ...props.modelValue, params: { ...props.modelValue.params } }
  mutator(next.params)
  emit('update:modelValue', next)
}
</script>

<template>
  <div class="field-grid field-grid-3">
    <label class="field">
      <span>亮度 (-1~1)</span>
      <input
        :value="Number(modelValue.params.brightness ?? 0)"
        type="number"
        step="0.05"
        min="-1"
        max="1"
        @input="patch((p) => (p.brightness = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>对比度 (0~3)</span>
      <input
        :value="Number(modelValue.params.contrast ?? 1)"
        type="number"
        step="0.05"
        min="0"
        max="3"
        @input="patch((p) => (p.contrast = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>饱和度 (0~3)</span>
      <input
        :value="Number(modelValue.params.saturation ?? 1)"
        type="number"
        step="0.05"
        min="0"
        max="3"
        @input="patch((p) => (p.saturation = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
  </div>
</template>
