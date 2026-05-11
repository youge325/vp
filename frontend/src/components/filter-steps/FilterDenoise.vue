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
  <div class="field-grid field-grid-2">
    <label class="field">
      <span>强度 (1~20)</span>
      <input
        :value="Number(modelValue.params.strength ?? 10)"
        type="number"
        min="1"
        max="20"
        @input="patch((p) => (p.strength = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>色彩强度 (1~20)</span>
      <input
        :value="Number(modelValue.params.colorStrength ?? 10)"
        type="number"
        min="1"
        max="20"
        @input="patch((p) => (p.colorStrength = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
  </div>
</template>
