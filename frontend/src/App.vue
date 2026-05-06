<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import StepRail from '@/components/StepRail.vue'
import { WORKBENCH_MODULES } from '@/views/registry'
import { useEnvStore } from '@/stores/env'
import { useBootstrap } from '@/composables/app/useBootstrap'
import { useEnvironmentChecker } from '@/composables/app/useEnvironmentChecker'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { getTaskStatusLabel } from '@/services/format/labels'
import type { WorkbenchModuleDefinition } from '@/types/view/modules'

const envStore = useEnvStore()
const route = useRoute()
const { recheckEnvironment } = useEnvironmentChecker()
const { batch, currentTaskItem } = useTaskOrchestrator()

useBootstrap()

const activeModule = computed<WorkbenchModuleDefinition>(
  () => (route.meta.module as WorkbenchModuleDefinition | undefined) ?? WORKBENCH_MODULES[0],
)

const topbarStatus = computed(() =>
  getTaskStatusLabel(batch, currentTaskItem.value?.taskState.status ?? null),
)
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
              v-if="envStore.env.issue && !envStore.env.isChecking"
              class="ghost-button compact-button"
              @click="recheckEnvironment()"
            >
              重试探测
            </button>
            <span class="status-pill" :data-state="topbarStatus">
              {{ envStore.env.isBootstrapping || envStore.env.isChecking ? 'checking' : topbarStatus }}
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
