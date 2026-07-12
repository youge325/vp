<script setup lang="ts">
import { computed } from 'vue'
import FilterNumberField from './FilterNumberField.vue'
import { createFilterModelParamsPatch } from '@/services/filters/filter-params'
import type { FilterCatalogEntry, FilterFieldDefinition } from '@/services/filters/filter-catalog'
import type { FilterStep } from '@/types/protocol'

const props = defineProps<{
  entry: FilterCatalogEntry
}>()

const modelValue = defineModel<FilterStep>({ required: true })
const patch = createFilterModelParamsPatch(modelValue)
const editor = computed(() => {
  if (!props.entry.editor) throw new Error(`Filter ${props.entry.kind} has no declarative editor`)
  return props.entry.editor
})

function fieldValue(field: FilterFieldDefinition): string | number | boolean {
  return modelValue.value.params[field.key] ?? props.entry.defaultParams[field.key] ?? ''
}

function updateNumber(field: FilterFieldDefinition, value: number): void {
  patch((params) => {
    params[field.key] = value
  })
}

function updateText(field: FilterFieldDefinition, event: Event): void {
  const value = (event.target as HTMLInputElement).value
  patch((params) => {
    params[field.key] = value
  })
}
</script>

<template>
  <div class="field-grid" :class="`field-grid-${editor.columns}`">
    <template v-for="field in editor.fields" :key="field.key">
      <FilterNumberField
        v-if="field.type === 'number'"
        :model-value="Number(fieldValue(field))"
        :label="field.label"
        :min="field.min"
        :max="field.max"
        :step="field.step"
        @update:model-value="updateNumber(field, $event)"
      />
      <label v-else class="field">
        <span>{{ field.label }}</span>
        <input :value="String(fieldValue(field))" type="text" @input="updateText(field, $event)" />
      </label>
    </template>
  </div>
</template>
