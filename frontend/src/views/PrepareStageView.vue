<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const overviewStats = computed(() => [
  { label: '运行时', value: store.env.checkResult?.runtime?.mode ?? '--' },
  { label: 'FFmpeg', value: store.env.checkResult?.ffmpeg?.available ? 'Ready' : 'Idle' },
  { label: 'GPU', value: store.env.checkResult?.gpu?.devices?.[0] ?? '--' },
  { label: '任务', value: store.task.status },
])
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>环境与概览</h2>
          <p class="panel-caption">主页模块聚合环境检查与当前工作台状态</p>
        </div>

        <div class="panel-actions">
          <button class="ghost-button" @click="store.pickInput()">选择素材</button>
          <button class="primary-button" :disabled="store.env.isChecking" @click="store.checkEnvironment()">
            {{ store.env.isChecking ? '检查中' : '检查环境' }}
          </button>
        </div>
      </div>

      <div class="stats-grid stats-grid-4">
        <article v-for="item in overviewStats" :key="item.label" class="stat-card stat-card-tall">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>工作台状态</h2>
          <p class="panel-caption">保留现有任务与配置映射，只调整信息承载位置</p>
        </div>
        <span class="panel-badge">统一壳层</span>
      </div>

      <div class="summary-grid">
        <article v-for="section in store.summarySections" :key="section.title" class="summary-block">
          <p class="summary-block-title">{{ section.title }}</p>
          <p v-for="line in section.lines" :key="line" class="summary-line">{{ line }}</p>
        </article>
      </div>
    </section>
  </div>
</template>
