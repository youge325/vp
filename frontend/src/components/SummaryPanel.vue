<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

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
  <aside class="summary-panel surface-panel">
    <div class="summary-topbar">
      <div>
        <p class="topbar-label">Status</p>
        <h2>侧栏</h2>
      </div>

      <button
        class="ghost-button compact-button"
        :disabled="!store.task.outputPath && !store.output.outputPath"
        @click="store.openOutputLocation()"
      >
        打开目录
      </button>
    </div>

    <section class="summary-grid">
      <article class="summary-card">
        <span>环境</span>
        <strong>{{ store.env.checkResult ? 'Ready' : 'Idle' }}</strong>
      </article>

      <article class="summary-card">
        <span>输入</span>
        <strong>{{ store.source.inputPath ? 'Ready' : 'Idle' }}</strong>
      </article>

      <article class="summary-card">
        <span>增强</span>
        <strong>{{ pipelineLabel }}</strong>
      </article>

      <article class="summary-card">
        <span>任务</span>
        <strong>{{ store.task.status }}</strong>
      </article>
    </section>

    <section class="summary-stack">
      <article v-for="section in store.summarySections" :key="section.title" class="summary-block">
        <p class="summary-block-title">{{ section.title }}</p>
        <p v-for="line in section.lines" :key="line" class="summary-line">{{ line }}</p>
      </article>
    </section>
  </aside>
</template>
