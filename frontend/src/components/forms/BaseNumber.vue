<script setup lang="ts">
// 数字输入控件:用 v-model 替代视图里满天飞的
//   :value="Number(...)" @input="setX(Number(($event.target as HTMLInputElement).value))"
// 模板,内建 min/max/step 钳制,且通过 `valueAsNumber` 拿到正确的数值类型。
// 不抛出 NaN——空输入或非数字会回退到 `modelValue`(保持上次有效值)。

import { computed } from 'vue'
import BaseField from './BaseField.vue'

const props = defineProps<{
  modelValue: number
  label: string
  min?: number
  max?: number
  step?: number
  hint?: string
  error?: string | null
  spanTwo?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: number): void
}>()

const displayValue = computed(() => Number.isFinite(props.modelValue) ? props.modelValue : 0)

function handleInput(event: Event): void {
  const target = event.target as HTMLInputElement
  const raw = target.valueAsNumber
  if (Number.isNaN(raw)) {
    return
  }
  let next = raw
  if (typeof props.min === 'number' && next < props.min) {
    next = props.min
  }
  if (typeof props.max === 'number' && next > props.max) {
    next = props.max
  }
  emit('update:modelValue', next)
}
</script>

<template>
  <BaseField :label="label" :hint="hint" :error="error" :span-two="spanTwo">
    <input
      :value="displayValue"
      type="number"
      :min="min"
      :max="max"
      :step="step"
      :placeholder="placeholder"
      @input="handleInput"
    />
  </BaseField>
</template>
