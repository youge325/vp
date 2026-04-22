<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const cards = computed(() => [
  { label: '环境', value: store.env.checkResult ? 'Ready' : store.env.issue ? 'Error' : 'Idle' },
  { label: '素材', value: `${store.mediaItems.length}` },
  { label: '已选', value: `${store.selectedIds.length}` },
  { label: '队列', value: store.batch.isRunning ? 'Running' : 'Idle' },
])
</script>

<template>
  <aside class="summary-panel surface-panel">
    <div class="summary-topbar">
      <div>
        <p class="topbar-label">Overview</p>
        <h2>摘要</h2>
      </div>

      <button class="ghost-button compact-button" :disabled="!store.resolvedOutputPath" @click="store.openOutputLocation()">
        打开目录
      </button>
    </div>

    <section class="summary-grid">
      <article v-for="item in cards" :key="item.label" class="summary-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
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
