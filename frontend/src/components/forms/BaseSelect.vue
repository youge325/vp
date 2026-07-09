<script setup lang="ts">
// 下拉选择控件:接受 `options: { value, label }[]`,
// 替代视图里 `<select :value="..." @change="setX(($event.target as HTMLSelectElement).value)">` 模板。

import BaseField from './BaseField.vue'
import type { SelectOption } from '@/types/view/select-option'

defineProps<{
  modelValue: string
  label: string
  options: readonly SelectOption[]
  hint?: string
  error?: string | null
  spanTwo?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
}>()

function handleChange(event: Event): void {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value)
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
