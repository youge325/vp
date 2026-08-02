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
  if (props.entry.kind !== modelValue.value.kind) {
    throw new Error(`Filter editor ${props.entry.kind} cannot edit ${modelValue.value.kind}`)
  }
  if (!props.entry.editor) throw new Error(`Filter ${props.entry.kind} has no declarative editor`)
  return props.entry.editor
})

function hasKey<Params extends object>(params: Params, key: PropertyKey): key is keyof Params {
  return key in params
}

function fieldValue(field: FilterFieldDefinition): string | number | boolean {
  const params = modelValue.value.params
  const defaults = props.entry.defaultStep.params
  const value = hasKey(params, field.key)
    ? params[field.key]
    : hasKey(defaults, field.key)
      ? defaults[field.key]
      : undefined
  return typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? value : ''
}

function updateNumber(field: FilterFieldDefinition, value: number): void {
  patch((params) => {
    Object.assign(params, { [field.key]: value })
  })
}

function updateText(field: FilterFieldDefinition, event: Event): void {
  if (!(event.target instanceof HTMLInputElement)) {
    throw new Error('Filter text update did not originate from an input')
  }
  const value = event.target.value
  patch((params) => {
    Object.assign(params, { [field.key]: value })
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
        <input
          :value="String(fieldValue(field))"
          type="text"
          :pattern="field.pattern"
          @input="updateText(field, $event)"
        />
      </label>
    </template>
  </div>
</template>
