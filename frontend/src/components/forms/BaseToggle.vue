<script setup lang="ts">
// 复选/开关控件:沿用 `.toggle-chip` 视觉,替代视图里
// `<label class="field toggle-field"><span>...</span><label class="toggle-chip"><input type="checkbox">` 模板。

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
  <label class="field toggle-field" :class="{ 'field-span-2': spanTwo }">
    <span>{{ label }}</span>
    <label class="toggle-chip">
      <input :checked="modelValue" type="checkbox" :disabled="disabled" @change="handleChange" />
      <span>{{ chipText ?? '启用' }}</span>
    </label>
  </label>
</template>
