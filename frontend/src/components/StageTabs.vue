<script setup lang="ts">
import type { StageTabDefinition } from '@/types'

defineProps<{
  items: StageTabDefinition[]
  modelValue: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="stage-tabs" role="tablist" aria-label="Stage tabs">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="stage-tab"
      :class="{ active: item.key === modelValue }"
      @click="emit('update:modelValue', item.key)"
    >
      {{ item.label }}
    </button>
  </div>
</template>
