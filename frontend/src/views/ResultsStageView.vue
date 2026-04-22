<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const runStats = computed(() => [
  { label: '状态', value: store.task.status },
  { label: '进度', value: `${store.task.percent.toFixed(1)}%` },
  { label: '阶段', value: store.task.stage || '--' },
  { label: '帧数', value: store.task.processedFrames ? `${store.task.processedFrames}` : '--' },
])

const renderSections = computed(() => store.summarySections.filter((section) => section.title !== '任务'))
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>渲染控制</h2>
          <p class="panel-caption">在独立模块中启动、停止并观察当前处理阶段</p>
        </div>

        <div class="panel-actions">
          <button
            v-if="store.task.status !== 'running'"
            class="primary-button"
            :disabled="!store.canStartTask"
            @click="store.startTask()"
          >
            开始流程
          </button>
          <button v-else class="danger-button" @click="store.cancelCurrentTask()">停止流程</button>
        </div>
      </div>

      <div class="stats-grid stats-grid-4">
        <article v-for="item in runStats" :key="item.label" class="stat-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>执行前检查</h2>
          <p class="panel-caption">渲染模块复用现有 store 摘要，便于开始前快速核对</p>
        </div>
      </div>

      <div class="summary-grid">
        <article v-for="section in renderSections" :key="section.title" class="summary-block">
          <p class="summary-block-title">{{ section.title }}</p>
          <p v-for="line in section.lines" :key="line" class="summary-line">{{ line }}</p>
        </article>
      </div>
    </section>
  </div>
</template>
