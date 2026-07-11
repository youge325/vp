<script setup lang="ts">
import type { FilterStep } from '@/types/protocol'
import { createFilterParamsPatch } from '@/services/filters/filter-params'

const props = defineProps<{
  modelValue: FilterStep
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: FilterStep): void
}>()

const INTERP_OPTIONS = [
  { value: 'lanczos4', label: 'Lanczos4' },
  { value: 'cubic', label: 'Cubic' },
  { value: 'area', label: 'Area' },
  { value: 'linear', label: 'Linear' },
]

const patch = createFilterParamsPatch(
  () => props.modelValue,
  (value) => emit('update:modelValue', value),
)
</script>

<template>
  <div class="field-grid field-grid-2">
    <label class="field">
      <span>模式</span>
      <select
        :value="modelValue.params.mode ?? 'factor'"
        @change="patch((p) => (p.mode = ($event.target as HTMLSelectElement).value))"
      >
        <option value="factor">缩放系数</option>
        <option value="resolution">目标分辨率</option>
      </select>
    </label>
    <label class="field">
      <span>插值算法</span>
      <select
        :value="modelValue.params.interpolation ?? 'lanczos4'"
        @change="patch((p) => (p.interpolation = ($event.target as HTMLSelectElement).value))"
      >
        <option v-for="opt in INTERP_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>
    </label>
    <label v-if="modelValue.params.mode === 'resolution'" class="field">
      <span>宽度</span>
      <input
        :value="Number(modelValue.params.width ?? 1920)"
        type="number"
        min="1"
        @input="patch((p) => (p.width = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label v-if="modelValue.params.mode === 'resolution'" class="field">
      <span>高度</span>
      <input
        :value="Number(modelValue.params.height ?? 1080)"
        type="number"
        min="1"
        @input="patch((p) => (p.height = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
    <label v-if="modelValue.params.mode !== 'resolution'" class="field">
      <span>缩放系数</span>
      <input
        :value="Number(modelValue.params.factor ?? 0.5)"
        type="number"
        step="0.01"
        min="0.01"
        max="10"
        @input="patch((p) => (p.factor = Number(($event.target as HTMLInputElement).value)))"
      />
    </label>
  </div>
</template>
