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
  <div class="field-grid field-grid-3">
    <label class="field">
      <span>上</span>
      <input
        :value="Number(modelValue.params.top ?? 0)"
        type="number"
        min="0"
        @input="patch((p) => (p.top = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>下</span>
      <input
        :value="Number(modelValue.params.bottom ?? 0)"
        type="number"
        min="0"
        @input="patch((p) => (p.bottom = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>左</span>
      <input
        :value="Number(modelValue.params.left ?? 0)"
        type="number"
        min="0"
        @input="patch((p) => (p.left = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>右</span>
      <input
        :value="Number(modelValue.params.right ?? 0)"
        type="number"
        min="0"
        @input="patch((p) => (p.right = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label class="field">
      <span>颜色 (hex)</span>
      <input
        :value="String(modelValue.params.color ?? '#000000')"
        type="text"
        @input="patch((p) => (p.color = ($event.target as HTMLInputElement).value))"
      />
    </label>
  </div>
</template>
