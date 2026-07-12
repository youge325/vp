<script setup lang="ts">
import BaseField from '@/components/forms/BaseField.vue'

defineProps<{
  modelValue: number
  label: string
  min?: number
  max?: number
  step?: number
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: number): void
}>()

function handleInput(event: Event): void {
  emit('update:modelValue', Number((event.target as HTMLInputElement).value))
}
</script>

<template>
  <BaseField :label="label">
    <input
      :value="modelValue"
      type="number"
      :min="min"
      :max="max"
      :step="step"
      @input="handleInput"
    />
  </BaseField>
</template>
