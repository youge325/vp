<script setup lang="ts">
import FilterNumberField from './FilterNumberField.vue'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

const modelValue = defineModel<FilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
</script>

<template>
  <div class="field-grid field-grid-2">
    <FilterNumberField
      :model-value="Number(modelValue.params.strength ?? 10)"
      label="强度 (1~20)"
      :min="1"
      :max="20"
      @update:model-value="patch((params) => (params.strength = $event))"
    />
    <FilterNumberField
      :model-value="Number(modelValue.params.colorStrength ?? 10)"
      label="色彩强度 (1~20)"
      :min="1"
      :max="20"
      @update:model-value="patch((params) => (params.colorStrength = $event))"
    />
  </div>
</template>
