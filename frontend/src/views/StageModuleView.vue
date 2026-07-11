<script setup lang="ts">
// Shared view for the preprocess and postprocess routes. Route props keep
// deep links stable while the stage value selects the corresponding chain.
//
import { computed } from 'vue'

import FilterChainEditor from '@/components/FilterChainEditor.vue'
import BaseToggle from '@/components/forms/BaseToggle.vue'
import { useFilterChainForm } from '@/composables/forms/useFilterChainForm'
import { useEditingScope } from '@/composables/selectors/useWorkbenchEditor'

type Stage = 'preprocess' | 'postprocess'

const props = defineProps<{ stage: Stage }>()

const { enabled, filters } = useFilterChainForm(() => props.stage)
const { targetLabel } = useEditingScope()

const title = computed(() => (props.stage === 'preprocess' ? '预处理' : '后处理'))
const toggleLabel = computed(() => (props.stage === 'preprocess' ? '启用预处理' : '启用后处理'))
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>{{ title }}</h2>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>

      <div class="field-grid field-grid-2">
        <BaseToggle v-model="enabled" :label="toggleLabel" />
      </div>

      <div v-if="enabled" class="filter-section">
        <FilterChainEditor v-model="filters" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.filter-section {
  margin-top: 16px;
}
</style>
