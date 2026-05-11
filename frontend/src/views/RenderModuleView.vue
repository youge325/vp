<script setup lang="ts">
import { computed } from 'vue'
import ResumeConflictDialog from '@/components/ResumeConflictDialog.vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { useOperationIssue } from '@/composables/selectors/useOperationIssue'
import type { ResumeConflictAction } from '@/types/domain/batch'

const {
  batch,
  pendingConflict,
  canStartBatch,
  startBatch,
  pauseCurrentTask,
  resumeCurrentTask,
  interruptBatch,
  resolveConflict,
} = useTaskOrchestrator()

const taskIssue = useOperationIssue('task')

const pauseButtonLabel = computed(() => (batch.isPaused ? '继续队列' : '暂停队列'))
const interruptButtonLabel = computed(() => (batch.isCancelling ? '中断中...' : '中断批次'))

function handleResolveConflict(action: ResumeConflictAction): void {
  void resolveConflict(action)
}
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
          <button class="primary-button" :disabled="!canStartBatch" @click="startBatch()">
            开始队列
          </button>
          <button
            class="ghost-button"
            :disabled="!batch.isRunning || batch.isCancelling"
            @click="batch.isPaused ? resumeCurrentTask() : pauseCurrentTask()"
          >
            {{ pauseButtonLabel }}
          </button>
          <button
            class="danger-button"
            :disabled="!batch.isRunning || batch.isCancelling"
            @click="interruptBatch()"
          >
            {{ interruptButtonLabel }}
          </button>
        </div>
      </div>

      <div v-if="taskIssue" class="info-banner info-banner-danger">
        <strong>任务操作失败</strong>
        <p>{{ taskIssue.message }}</p>
      </div>
    </section>

    <TaskConsole />

    <ResumeConflictDialog
      v-if="pendingConflict"
      :descriptor="pendingConflict"
      @resolve="handleResolveConflict"
    />
  </div>
</template>
