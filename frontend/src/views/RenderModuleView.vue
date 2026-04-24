<script setup lang="ts">
import { computed } from 'vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const taskOperationIssue = computed(() =>
  store.operationIssue?.scope === 'task' ? store.operationIssue.error : null,
)
const pauseButtonLabel = computed(() => (store.batch.isPaused ? '继续队列' : '暂停队列'))
const interruptButtonLabel = computed(() => (store.batch.isCancelling ? '中断中...' : '中断批次'))
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
          <button class="primary-button" :disabled="!store.canStartBatch" @click="store.startBatch()">
            开始队列
          </button>
          <button
            class="ghost-button"
            :disabled="!store.batch.isRunning || store.batch.isCancelling"
            @click="store.batch.isPaused ? store.resumeCurrentTask() : store.pauseCurrentTask()"
          >
            {{ pauseButtonLabel }}
          </button>
          <button
            class="danger-button"
            :disabled="!store.batch.isRunning || store.batch.isCancelling"
            @click="store.interruptBatch()"
          >
            {{ interruptButtonLabel }}
          </button>
        </div>
      </div>

      <div v-if="taskOperationIssue" class="info-banner info-banner-danger">
        <strong>任务操作失败</strong>
        <p>{{ taskOperationIssue.message }}</p>
      </div>
    </section>

    <TaskConsole />
  </div>
</template>
