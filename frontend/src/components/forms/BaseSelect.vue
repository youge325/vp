<script setup lang="ts" generic="Value extends string">
// Typed select: the option value union is preserved through v-model.

import BaseField from './BaseField.vue'
import type { SelectOption } from '@/types/view/select-option'

defineProps<{
  modelValue: Value
  label: string
  options: readonly SelectOption<Value>[]
  hint?: string
  error?: string | null
  spanTwo?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: Value): void
}>()

function handleChange(event: Event): void {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value as Value)
}
</script>

<template>
  <BaseField :label="label" :hint="hint" :error="error" :span-two="spanTwo">
    <select :value="modelValue" :disabled="disabled" @change="handleChange">
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>
  </BaseField>
</template>
