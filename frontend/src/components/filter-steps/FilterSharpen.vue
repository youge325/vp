<script setup lang="ts">
import type { FilterStep } from '@/types/protocol'
import { createFilterParamsPatch } from '@/services/filters/filter-params'

const props = defineProps<{
  modelValue: FilterStep
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: FilterStep): void
}>()

const patch = createFilterParamsPatch(
  () => props.modelValue,
  (value) => emit('update:modelValue', value),
)
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
