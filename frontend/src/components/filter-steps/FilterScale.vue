<script setup lang="ts">
import BaseSelect from '@/components/forms/BaseSelect.vue'
import FilterNumberField from './FilterNumberField.vue'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

type ScaleFilterStep = Extract<FilterStep, { kind: 'scale' }>

const MODE_OPTIONS = [
  { value: 'factor', label: '缩放系数' },
  { value: 'resolution', label: '目标分辨率' },
] as const

const INTERP_OPTIONS = [
  { value: 'lanczos4', label: 'Lanczos4' },
  { value: 'cubic', label: 'Cubic' },
  { value: 'area', label: 'Area' },
  { value: 'linear', label: 'Linear' },
] as const

const modelValue = defineModel<ScaleFilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
</script>

<template>
  <div class="field-grid field-grid-2">
    <BaseSelect
      :model-value="modelValue.params.mode ?? 'factor'"
      label="模式"
      :options="MODE_OPTIONS"
      @update:model-value="patch((params) => (params.mode = $event))"
    />
    <BaseSelect
      :model-value="modelValue.params.interpolation ?? 'lanczos4'"
      label="插值算法"
      :options="INTERP_OPTIONS"
      @update:model-value="patch((params) => (params.interpolation = $event))"
    />
    <FilterNumberField
      v-if="modelValue.params.mode === 'resolution'"
      :model-value="Number(modelValue.params.width ?? 1920)"
      label="宽度"
      :min="1"
      @update:model-value="patch((params) => (params.width = $event))"
    />
    <FilterNumberField
      v-if="modelValue.params.mode === 'resolution'"
      :model-value="Number(modelValue.params.height ?? 1080)"
      label="高度"
      :min="1"
      @update:model-value="patch((params) => (params.height = $event))"
    />
    <FilterNumberField
      v-if="modelValue.params.mode !== 'resolution'"
      :model-value="Number(modelValue.params.factor ?? 0.5)"
      label="缩放系数"
      :step="0.01"
      :min="0.01"
      :max="10"
      @update:model-value="patch((params) => (params.factor = $event))"
    />
  </div>
</template>
