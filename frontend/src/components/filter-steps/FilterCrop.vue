<script setup lang="ts">
import FilterNumberField from './FilterNumberField.vue'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

const modelValue = defineModel<FilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
</script>

<template>
  <div class="field-grid field-grid-4">
    <FilterNumberField :model-value="Number(modelValue.params.x ?? 0)" label="X" :min="0" @update:model-value="patch((params) => (params.x = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.y ?? 0)" label="Y" :min="0" @update:model-value="patch((params) => (params.y = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.width ?? 1920)" label="宽度" :min="1" @update:model-value="patch((params) => (params.width = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.height ?? 1080)" label="高度" :min="1" @update:model-value="patch((params) => (params.height = $event))" />
  </div>
</template>
