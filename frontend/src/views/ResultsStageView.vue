<script setup lang="ts">
import { computed } from 'vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const taskOperationIssue = computed(() =>
  store.operationIssue?.scope === 'task' ? store.operationIssue.error : null,
)

const runStats = computed(() => [
  { label: '批次总数', value: `${store.batchTotal}` },
  { label: '已完成', value: `${store.batch.completedCount}` },
  { label: '失败/取消', value: `${store.batch.failedCount}` },
  { label: '当前任务', value: store.currentTaskItem?.displayName ?? '--' },
])
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>批处理队列</h2>
          <p class="panel-caption">渲染页现在只保留批次控制和运行日志。任务结束后不会保留结果历史。</p>
        </div>

        <div class="panel-actions">
          <button
            v-if="!store.batch.isRunning"
            class="primary-button"
            :disabled="!store.canStartBatch"
            @click="store.startBatch()"
          >
            开始队列
          </button>
          <button v-else class="danger-button" @click="store.cancelCurrentTask()">取消当前项</button>
        </div>
      </div>

      <div v-if="taskOperationIssue" class="info-banner info-banner-danger">
        <strong>任务操作失败</strong>
        <p>{{ taskOperationIssue.message }}</p>
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
