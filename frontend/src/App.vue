<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import StepRail from '@/components/StepRail.vue'
import { WORKBENCH_MODULES } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { WorkbenchModuleDefinition } from '@/types'

const store = useWorkbenchStore()
const route = useRoute()

const activeModule = computed<WorkbenchModuleDefinition>(
  () => (route.meta.module as WorkbenchModuleDefinition | undefined) ?? WORKBENCH_MODULES[0],
)

const topbarStatus = computed(() => {
  if (store.batch.isRunning) {
    return 'running'
  }
  return store.globalTaskStatus
})

onMounted(() => {
  void store.bootstrap()
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
        <header class="topbar">
          <div class="topbar-copy">
            <p class="topbar-label">VP Desktop</p>
            <div class="topbar-title-row">
              <h1>{{ activeModule.title }}</h1>
              <span class="topbar-divider" />
              <span class="topbar-tab">{{ activeModule.description }}</span>
            </div>
          </div>

          <div class="topbar-actions">
            <button
              v-if="store.env.issue && !store.env.isChecking"
              class="ghost-button compact-button"
              @click="store.recheckEnvironment()"
            >
              重试探测
            </button>
            <button
              v-if="store.resolvedOutputPath"
              class="ghost-button compact-button"
              @click="store.openOutputLocation()"
            >
              打开输出
            </button>
            <span class="status-pill" :data-state="topbarStatus">
              {{ store.env.isBootstrapping || store.env.isChecking ? 'checking' : topbarStatus }}
            </span>
          </div>
        </header>

        <section class="content-surface">
          <RouterView />
        </section>
      </main>
    </div>
  </div>
</template>
