<script setup lang="ts">
import FilterChainEditor from '@/components/FilterChainEditor.vue'
import { useFilterChainForm } from '@/composables/forms/useFilterChainForm'
import { useEditingScope } from '@/composables/selectors/useWorkbenchEditor'

const { enabled, filters } = useFilterChainForm('preprocess')
const { targetLabel, caption } = useEditingScope('preprocess')
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>预处理</h2>
          <p class="panel-caption">{{ caption }}</p>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field toggle-field">
          <span>启用预处理</span>
          <label class="toggle-chip">
            <input v-model="enabled" type="checkbox" />
            <span>启用</span>
          </label>
        </label>
      </div>

      <div v-if="enabled" class="filter-section">
        <p class="panel-caption">位于 解码 → 增强 之间</p>
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
