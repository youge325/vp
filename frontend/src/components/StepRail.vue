<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { WORKBENCH_STAGES } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { StageDefinition, StageKey } from '@/types'

const route = useRoute()
const store = useWorkbenchStore()

const activeStageKey = computed<StageKey | undefined>(() => {
  const stage = route.meta.stage as StageDefinition | undefined
  return stage?.key
})

const stageStates = computed<Record<StageKey, string>>(() => ({
  prepare: store.env.checkResult || store.source.inputPath ? 'ready' : 'idle',
  enhance:
    store.workflow.enableInterpolation || store.workflow.enableSuperResolution || store.anime.enabled
      ? 'ready'
      : 'idle',
  deliver: store.source.inputPath ? 'ready' : 'idle',
  results: store.task.status === 'completed' ? 'done' : store.task.status === 'running' ? 'ready' : 'idle',
}))

const footerStats = computed(() => [
  {
    label: '环境',
    value: store.env.checkResult ? 'Ready' : 'Idle',
  },
  {
    label: '输入',
    value: store.source.inputPath ? 'Ready' : 'Idle',
  },
  {
    label: '任务',
    value: store.task.status,
  },
])
</script>

<template>
  <aside class="rail-column surface-panel">
    <div class="rail-brand">
      <p class="topbar-label">Desktop</p>
      <h2>VP</h2>
    </div>

    <nav class="rail-nav">
      <RouterLink
        v-for="stage in WORKBENCH_STAGES"
        :key="stage.key"
        :to="stage.path"
        class="rail-link"
        :class="{ active: activeStageKey === stage.key }"
      >
        <span class="rail-link-index">{{ stage.index.toString().padStart(2, '0') }}</span>
        <span class="rail-link-copy">
          <strong>{{ stage.title }}</strong>
          <small>{{ stage.path.replace('/', '').toUpperCase() }}</small>
        </span>
        <span class="rail-state-dot" :data-state="stageStates[stage.key]" />
      </RouterLink>
    </nav>

    <section class="rail-footer">
      <article v-for="item in footerStats" :key="item.label" class="rail-mini-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </section>
  </aside>
</template>
