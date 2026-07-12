<script setup lang="ts">
import FilterNumberField from './FilterNumberField.vue'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

const modelValue = defineModel<FilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
</script>

<template>
  <div class="field-grid field-grid-3">
    <FilterNumberField :model-value="Number(modelValue.params.brightness ?? 0)" label="亮度 (-1~1)" :step="0.05" :min="-1" :max="1" @update:model-value="patch((params) => (params.brightness = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.contrast ?? 1)" label="对比度 (0~3)" :step="0.05" :min="0" :max="3" @update:model-value="patch((params) => (params.contrast = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.saturation ?? 1)" label="饱和度 (0~3)" :step="0.05" :min="0" :max="3" @update:model-value="patch((params) => (params.saturation = $event))" />
  </div>
</template>
