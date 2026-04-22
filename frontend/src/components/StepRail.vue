<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { WORKBENCH_MODULES } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { ModuleKey, WorkbenchModuleDefinition } from '@/types'

const route = useRoute()
const store = useWorkbenchStore()

const activeModuleKey = computed<ModuleKey>(() => {
  const module = route.meta.module as WorkbenchModuleDefinition | undefined
  return module?.key ?? WORKBENCH_MODULES[0].key
})

const moduleStates = computed<Record<ModuleKey, string>>(() => ({
  home: store.env.checkResult || store.source.inputPath || store.task.status !== 'idle' ? 'ready' : 'idle',
  input: store.source.inputPath ? 'ready' : 'idle',
  enhance:
    store.workflow.enableInterpolation || store.workflow.enableSuperResolution || store.anime.enabled
      ? 'ready'
      : 'idle',
  encode: store.source.inputPath ? 'ready' : 'idle',
  render: store.task.status === 'completed' ? 'done' : store.task.status === 'running' ? 'ready' : 'idle',
  preview: store.task.logs.length > 0 || store.task.outputPath || store.output.outputPath ? 'ready' : 'idle',
}))

const pipelineLabel = computed(() => {
  const enabled = [
    store.workflow.enableInterpolation ? '补帧' : null,
    store.workflow.enableSuperResolution ? '超分' : null,
    store.anime.enabled ? '动漫' : null,
  ].filter(Boolean)

  return enabled.length > 0 ? enabled.join(' / ') : '纯转码'
})
</script>

<template>
  <aside class="rail-column">
    <div class="rail-brand">
      <p class="topbar-label">Workbench</p>
      <h2>VP</h2>
      <p class="rail-brand-copy">统一模块壳层</p>
    </div>

    <nav class="rail-nav">
      <RouterLink
        v-for="module in WORKBENCH_MODULES"
        :key="module.key"
        :to="module.path"
        :title="module.title"
        class="rail-link"
        :class="{ active: activeModuleKey === module.key }"
        :data-state="moduleStates[module.key]"
      >
        <span class="rail-link-icon">
          <component :is="module.icon" />
        </span>
        <span class="rail-link-copy">
          <strong>{{ module.title }}</strong>
          <small>{{ module.description }}</small>
        </span>
        <span class="rail-state-dot" :data-state="moduleStates[module.key]" />
      </RouterLink>
    </nav>

    <section class="rail-footer">
      <span class="rail-footer-chip">{{ pipelineLabel }}</span>
      <span class="rail-footer-chip" :data-state="store.task.status">任务 {{ store.task.status }}</span>
    </section>
  </aside>
</template>
