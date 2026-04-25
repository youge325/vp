<script setup lang="ts">
import { computed } from 'vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useEnvStore } from '@/stores/env'
import { useTaskStore } from '@/stores/task'

const envStore = useEnvStore()
const taskStore = useTaskStore()

const taskOperationIssue = computed(() =>
  envStore.operationIssue?.scope === 'task' ? envStore.operationIssue.error : null,
)
const pauseButtonLabel = computed(() => (taskStore.batch.isPaused ? '继续队列' : '暂停队列'))
const interruptButtonLabel = computed(() => (taskStore.batch.isCancelling ? '中断中...' : '中断批次'))
</script>

<template>
  <div class="module-stack render-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>批处理队列</h2>
          <p class="panel-caption">渲染页现在只保留批次控制和运行日志。任务结束后不会保留结果历史。</p>
        </div>

        <div class="panel-actions">
          <button class="primary-button" :disabled="!taskStore.canStartBatch" @click="taskStore.startBatch()">
            开始队列
          </button>
          <button
            class="ghost-button"
            :disabled="!taskStore.batch.isRunning || taskStore.batch.isCancelling"
            @click="taskStore.batch.isPaused ? taskStore.resumeCurrentTask() : taskStore.pauseCurrentTask()"
          >
            {{ pauseButtonLabel }}
          </button>
          <button
            class="danger-button"
            :disabled="!taskStore.batch.isRunning || taskStore.batch.isCancelling"
            @click="taskStore.interruptBatch()"
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
