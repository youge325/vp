<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import StepRail from '@/components/StepRail.vue'
import SummaryPanel from '@/components/SummaryPanel.vue'
import { useWorkbenchStore } from '@/stores/workbench'
import type { StepDefinition } from '@/types'

const store = useWorkbenchStore()
const route = useRoute()

const activeStep = computed<StepDefinition | undefined>(() => route.meta.step as StepDefinition)

onMounted(async () => {
  await store.attachTaskListeners()
})

onBeforeUnmount(() => {
  store.detachTaskListeners()
})
</script>

<template>
  <div class="app-shell">
    <div class="app-backdrop" />
    <StepRail />

    <main class="workspace-shell">
      <header class="workspace-header surface-panel">
        <div>
          <p class="eyebrow">VP Workbench</p>
          <h1>{{ activeStep?.title ?? '视频处理工作台' }}</h1>
          <p class="subtle">
            {{ activeStep?.subtitle ?? '围绕 CLI 内核的 Tauri 多平台工作台。' }}
          </p>
        </div>

        <div class="header-actions">
          <span class="status-pill" :data-state="store.task.status">
            {{ store.task.status }}
          </span>
          <span class="status-pill" :data-state="store.env.checkResult ? 'ready' : 'pending'">
            {{ store.env.checkResult ? 'environment-checked' : 'environment-pending' }}
          </span>
        </div>
      </header>

      <section class="workspace-body">
        <div class="workspace-content surface-panel">
          <RouterView />
        </div>

        <SummaryPanel />
      </section>
    </main>
  </div>
</template>
