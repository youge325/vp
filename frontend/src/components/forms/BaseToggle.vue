<script setup lang="ts">
import BaseField from './BaseField.vue'

defineProps<{
  modelValue: boolean
  label: string
  /** chip 内的开关文案(默认 "启用")。 */
  chipText?: string
  spanTwo?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

function handleChange(event: Event): void {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.checked)
}
</script>

<template>
  <BaseField :label="label" :span-two="spanTwo" toggle>
    <span class="toggle-chip">
      <input :checked="modelValue" type="checkbox" :disabled="disabled" @change="handleChange" />
      <span>{{ chipText ?? '启用' }}</span>
    </span>
  </BaseField>
</template>
