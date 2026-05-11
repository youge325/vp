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
      <span>强度 (0~1)</span>
      <input
        :value="Number(modelValue.params.amount ?? 0.5)"
        type="number"
        step="0.05"
        min="0"
        max="1"
        @input="patch((p) => (p.amount = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
  </div>
</template>
