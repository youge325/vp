<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import IssueBanner from '@/components/IssueBanner.vue'
import StepRail from '@/components/StepRail.vue'
import { WORKBENCH_MODULE_BY_KEY } from '@/views/registry'
import { useBootstrap } from '@/composables/app/useBootstrap'
import { useEnvironmentChecker } from '@/composables/app/useEnvironmentChecker'
import { useOperationIssue } from '@/composables/selectors/useOperationIssue'
import { getTaskStatusLabel } from '@/services/format/labels'
import { useEnvStore } from '@/stores/env'
import { useTaskStore } from '@/stores/task'
import type { WorkbenchModuleDefinition } from '@/types/view/modules'

const route = useRoute()
const { recheckEnvironment } = useEnvironmentChecker()
const envStore = useEnvStore()
const taskStore = useTaskStore()
const taskStatusLabel = computed(() => getTaskStatusLabel(taskStore.batch))
const presetIssue = useOperationIssue('preset')

useBootstrap()

const activeModule = computed<WorkbenchModuleDefinition>(
  () => route.meta.module ?? WORKBENCH_MODULE_BY_KEY.home,
)

const isBusy = computed(() => envStore.env.isBootstrapping || envStore.env.isChecking)
</script>

<template>
  <div class="app-viewport">
    <div class="app-shell" data-testid="app-shell">
      <StepRail />

      <main class="center-column">
        <header class="topbar">
          <div class="topbar-copy">
            <p class="topbar-label">VP Desktop</p>
            <div class="topbar-title-row">
              <h1>{{ activeModule.title }}</h1>
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
            <span class="status-pill" :data-state="taskStatusLabel">
              {{ isBusy ? 'checking' : taskStatusLabel }}
            </span>
          </div>
        </header>

        <section class="content-surface">
          <IssueBanner
            class="global-issue-banner"
            :issue="presetIssue"
            title="预设持久化失败"
          />
          <RouterView />
        </section>
      </main>
    </div>
  </div>
</template>
