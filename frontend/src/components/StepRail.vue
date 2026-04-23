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
  home: store.env.checkResult || store.env.issue ? 'ready' : 'idle',
  input: store.mediaItems.length > 0 ? 'ready' : 'idle',
  decode: store.env.checkResult ? 'ready' : 'idle',
  enhance: store.env.checkResult ? 'ready' : 'idle',
  encode: store.env.checkResult && store.visibleEncoderProfiles.length > 0 ? 'ready' : 'idle',
  render: store.batch.isRunning || store.canStartBatch ? 'ready' : 'idle',
}))

const workflowLabel = computed(() => {
  const workflow = store.editor.workflowConfig
  const enabled = [
    workflow.interpolation.enabled ? '补帧' : null,
    workflow.superResolution.enabled ? '超分' : null,
    workflow.anime.enabled ? '动漫' : null,
  ].filter(Boolean)

  return enabled.length > 0 ? enabled.join(' / ') : '转码'
})

const selectionLabel = computed(() =>
  store.editingScope === 'preset'
    ? '默认预设'
    : `${store.selectedIds.length || 1}/${store.mediaItems.length} 已选`,
)
</script>

<template>
  <aside class="rail-column">
    <div class="rail-brand">
      <p class="topbar-label">Workbench</p>
      <h2>VP</h2>
      <p class="rail-brand-copy">批量视频处理工作台</p>
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
      <span class="rail-footer-chip">{{ workflowLabel }}</span>
      <span class="rail-footer-chip">{{ selectionLabel }}</span>
      <span class="rail-footer-chip" :data-state="store.globalTaskStatus">任务 {{ store.globalTaskStatus }}</span>
    </section>
  </aside>
</template>
