<script setup lang="ts">
// Phase 7b — Shared scaffold for the pre-/post-process stage views.
//
// ``PreprocessModuleView`` and ``PostprocessModuleView`` used to be
// 38-line copies of each other that differed in three string
// fields (stage name, panel title, pipeline-position caption).
// They keep their own router entries (so deep links and breadcrumbs
// still work) but defer to this component for the actual layout.
//
// If a future requirement makes the two stages diverge (different
// filter sets, different gating logic, …), revert this collapse —
// the right answer at that point is two distinct views, not a
// ``stage``-flag matrix here.
import { computed } from 'vue'

import FilterChainEditor from '@/components/FilterChainEditor.vue'
import BaseToggle from '@/components/forms/BaseToggle.vue'
import { useFilterChainForm } from '@/composables/forms/useFilterChainForm'
import { useEditingScope } from '@/composables/selectors/useWorkbenchEditor'

type Stage = 'preprocess' | 'postprocess'

const props = defineProps<{ stage: Stage }>()

const { enabled, filters } = useFilterChainForm(props.stage)
const { targetLabel, caption } = useEditingScope(props.stage)

const title = computed(() => (props.stage === 'preprocess' ? '预处理' : '后处理'))
const toggleLabel = computed(() => (props.stage === 'preprocess' ? '启用预处理' : '启用后处理'))
const pipelinePosition = computed(() =>
  props.stage === 'preprocess' ? '位于 解码 → 增强 之间' : '位于 增强 → 编码 之间',
)
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>{{ title }}</h2>
          <p class="panel-caption">{{ caption }}</p>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>

      <div class="field-grid field-grid-2">
        <BaseToggle v-model="enabled" :label="toggleLabel" />
      </div>

      <div v-if="enabled" class="filter-section">
        <p class="panel-caption">{{ pipelinePosition }}</p>
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
