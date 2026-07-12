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
      :model-value="Number(modelValue.params.amount ?? 0.5)"
      label="强度 (0~1)"
      :step="0.05"
      :min="0"
      :max="1"
      @update:model-value="patch((params) => (params.amount = $event))"
    />
  </div>
</template>
