<script setup lang="ts">
import { computed } from 'vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const runStats = computed(() => [
  { label: '状态', value: store.task.status },
  { label: '进度', value: `${store.task.percent.toFixed(1)}%` },
  { label: '阶段', value: store.task.stage || '--' },
  { label: '帧数', value: store.task.processedFrames ? `${store.task.processedFrames}` : '--' },
])
</script>

<template>
  <div class="stage-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <h2>流程</h2>
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

    <TaskConsole />
  </div>
</template>
