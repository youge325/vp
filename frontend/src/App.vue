<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import StepRail from '@/components/StepRail.vue'
import { WORKBENCH_MODULES } from '@/lib/workflow'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { useTaskStore } from '@/stores/task'
import { createDefaultWorkbenchPreset } from '@/lib/task-mapper'
import { getTaskStatusLabel } from '@/services/format'
import type { WorkbenchModuleDefinition } from '@/types'

const envStore = useEnvStore()
const presetStore = usePresetStore()
const taskStore = useTaskStore()
const route = useRoute()

const activeModule = computed<WorkbenchModuleDefinition>(
  () => (route.meta.module as WorkbenchModuleDefinition | undefined) ?? WORKBENCH_MODULES[0],
)

const topbarStatus = computed(() =>
  getTaskStatusLabel(taskStore.batch, taskStore.currentTaskItem?.taskState.status ?? null),
)

async function bootstrap(): Promise<void> {
  if (envStore.env.isBootstrapping) {
    return
  }
  envStore.env.isBootstrapping = true
  try {
    await taskStore.attachTaskListeners()
    const hasPersistedPreset = await presetStore.loadPersistedPreset()
    await envStore.recheckEnvironment(false)
    if (!hasPersistedPreset && envStore.env.checkResult) {
      presetStore.replaceDraftPreset(createDefaultWorkbenchPreset(envStore.env.checkResult))
    }
    presetStore.presetPersistenceReady = true
    presetStore.schedulePresetSave()
  } finally {
    envStore.env.isBootstrapping = false
  }
}

onMounted(() => {
  void bootstrap()
})

onBeforeUnmount(() => {
  taskStore.detachTaskListeners()
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
              v-if="envStore.env.issue && !envStore.env.isChecking"
              class="ghost-button compact-button"
              @click="envStore.recheckEnvironment()"
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
