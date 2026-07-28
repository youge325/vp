<script setup lang="ts">
import type { MetricRow } from '@/types/view/model-metrics'

defineProps<{
  label: string
  rows: readonly MetricRow[]
  compact?: boolean
}>()
</script>

<template>
  <div
    v-if="rows.length"
    class="model-metric-grid"
    :class="{ 'model-metric-grid-compact': compact }"
    :aria-label="label"
  >
    <div v-for="row in rows" :key="row.label" class="model-metric-item">
      <span>{{ row.label }}</span>
      <strong>{{ row.value }}</strong>
    </div>
  </div>
</template>
