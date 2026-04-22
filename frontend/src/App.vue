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

const resolvedOutputPath = computed(() => store.task.outputPath || store.output.outputPath)

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
              class="ghost-button compact-button"
              :disabled="store.env.isChecking"
              @click="store.checkEnvironment()"
            >
              {{ store.env.isChecking ? '检查中' : '检查环境' }}
            </button>
            <button v-if="resolvedOutputPath" class="ghost-button compact-button" @click="store.openOutputLocation()">
              打开输出
            </button>
            <span class="status-pill" :data-state="store.task.status">{{ store.task.status }}</span>
          </div>
        </header>

        <section class="content-surface">
          <RouterView />
        </section>
      </main>
    </div>
  </div>
</template>
