<script setup lang="ts">
import FilterNumberField from './FilterNumberField.vue'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import type { FilterStep } from '@/types/protocol'

const modelValue = defineModel<FilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
</script>

<template>
  <div class="field-grid field-grid-3">
    <FilterNumberField :model-value="Number(modelValue.params.top ?? 0)" label="上" :min="0" @update:model-value="patch((params) => (params.top = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.bottom ?? 0)" label="下" :min="0" @update:model-value="patch((params) => (params.bottom = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.left ?? 0)" label="左" :min="0" @update:model-value="patch((params) => (params.left = $event))" />
    <FilterNumberField :model-value="Number(modelValue.params.right ?? 0)" label="右" :min="0" @update:model-value="patch((params) => (params.right = $event))" />
    <label class="field">
      <span>颜色 (hex)</span>
      <input
        :value="String(modelValue.params.color ?? '#000000')"
        type="text"
        @input="patch((params) => (params.color = ($event.target as HTMLInputElement).value))"
      />
    </label>
  </div>
</template>
