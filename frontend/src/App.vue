<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import StepRail from '@/components/StepRail.vue'
import SummaryPanel from '@/components/SummaryPanel.vue'
import { PREPARE_TABS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { StageDefinition } from '@/types'

const store = useWorkbenchStore()
const route = useRoute()

const activeStage = computed<StageDefinition | undefined>(() => route.meta.stage as StageDefinition)

const stageCaption = computed(() => {
  if (activeStage.value?.key === 'prepare') {
    const raw = Array.isArray(route.query.tab) ? route.query.tab[0] : route.query.tab
    const tab = typeof raw === 'string' ? raw : 'environment'
    return PREPARE_TABS.find((item) => item.key === tab)?.label ?? PREPARE_TABS[0].label
  }

  if (activeStage.value?.key === 'enhance') {
    return '单管道'
  }

  if (activeStage.value?.key === 'deliver') {
    return '编解码'
  }

  return 'CLI'
})

onMounted(async () => {
  await store.attachTaskListeners()
})

onBeforeUnmount(() => {
  store.detachTaskListeners()
})
</script>

<template>
  <div class="app-viewport">
    <div class="app-shell">
      <StepRail />

      <main class="center-column">
        <header class="topbar surface-panel">
          <div class="topbar-copy">
            <p class="topbar-label">VP Workbench</p>
            <div class="topbar-title-row">
              <h1>{{ activeStage?.title ?? '工作台' }}</h1>
              <span class="topbar-divider" />
              <span class="topbar-tab">{{ stageCaption }}</span>
            </div>
          </div>

          <div class="topbar-actions">
            <button
              class="ghost-button compact-button"
              :disabled="store.env.isChecking"
              @click="store.checkEnvironment()"
            >
              {{ store.env.isChecking ? '检查中' : '检查环境' }}
            </button>
            <span class="status-pill" :data-state="store.task.status">{{ store.task.status }}</span>
          </div>
        </header>

        <section class="content-surface surface-panel">
          <RouterView />
        </section>
      </main>

      <SummaryPanel />
    </div>
  </div>
</template>
