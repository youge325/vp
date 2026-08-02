<script setup lang="ts">
import BaseSelect from '@/components/forms/BaseSelect.vue'
import FilterNumberField from './FilterNumberField.vue'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import { APPLICATION_DEFAULTS, FILTER_FIELD_CONSTRAINTS } from '@/types/protocol'
import type { FilterStep } from '@/types/protocol'

type ScaleFilterStep = Extract<FilterStep, { kind: 'scale' }>

const MODE_LABELS = {
  factor: '缩放系数',
  resolution: '目标分辨率',
} as const
const MODE_OPTIONS = FILTER_FIELD_CONSTRAINTS.scale.mode.enum.map((value) => ({
  value,
  label: MODE_LABELS[value],
}))

const INTERPOLATION_LABELS = {
  lanczos4: 'Lanczos4',
  cubic: 'Cubic',
  area: 'Area',
  linear: 'Linear',
} as const
const INTERP_OPTIONS = FILTER_FIELD_CONSTRAINTS.scale.interpolation.enum.map((value) => ({
  value,
  label: INTERPOLATION_LABELS[value],
}))

const defaults = APPLICATION_DEFAULTS.filters.scale
const constraints = FILTER_FIELD_CONSTRAINTS.scale
const factorStep = 0.01

const modelValue = defineModel<ScaleFilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
</script>

<template>
  <div class="field-grid field-grid-2">
    <BaseSelect
      :model-value="modelValue.params.mode ?? defaults.mode"
      label="模式"
      :options="MODE_OPTIONS"
      @update:model-value="patch((params) => (params.mode = $event))"
    />
    <BaseSelect
      :model-value="modelValue.params.interpolation ?? defaults.interpolation"
      label="插值算法"
      :options="INTERP_OPTIONS"
      @update:model-value="patch((params) => (params.interpolation = $event))"
    />
    <FilterNumberField
      v-if="modelValue.params.mode === 'resolution'"
      :model-value="Number(modelValue.params.width ?? defaults.width)"
      label="宽度"
      :min="constraints.width.minimum"
      @update:model-value="patch((params) => (params.width = $event))"
    />
    <FilterNumberField
      v-if="modelValue.params.mode === 'resolution'"
      :model-value="Number(modelValue.params.height ?? defaults.height)"
      label="高度"
      :min="constraints.height.minimum"
      @update:model-value="patch((params) => (params.height = $event))"
    />
    <FilterNumberField
      v-if="modelValue.params.mode !== 'resolution'"
      :model-value="Number(modelValue.params.factor ?? defaults.factor)"
      label="缩放系数"
      :step="factorStep"
      :min="constraints.factor.exclusiveMinimum + factorStep"
      @update:model-value="patch((params) => (params.factor = $event))"
    />
  </div>
</template>
