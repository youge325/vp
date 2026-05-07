<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { WORKBENCH_MODULES } from '@/views/registry'
import { useStepRailState } from '@/composables/selectors/useStepRailState'

const { activeModuleKey, moduleStates, workflowLabel, selectionLabel, taskStatusLabel } = useStepRailState()
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
      <span class="rail-footer-chip" :data-state="taskStatusLabel">任务 {{ taskStatusLabel }}</span>
    </section>
  </aside>
</template>
