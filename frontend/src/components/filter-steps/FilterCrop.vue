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
  <div class="field-grid field-grid-4">
    <label class="field">
      <span>X</span>
      <input
        :value="Number(modelValue.params.x ?? 0)"
        type="number"
        min="0"
        @input="patch((p) => (p.x = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>Y</span>
      <input
        :value="Number(modelValue.params.y ?? 0)"
        type="number"
        min="0"
        @input="patch((p) => (p.y = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>宽度</span>
      <input
        :value="Number(modelValue.params.width ?? 1920)"
        type="number"
        min="1"
        @input="patch((p) => (p.width = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>高度</span>
      <input
        :value="Number(modelValue.params.height ?? 1080)"
        type="number"
        min="1"
        @input="patch((p) => (p.height = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
  </div>
</template>
