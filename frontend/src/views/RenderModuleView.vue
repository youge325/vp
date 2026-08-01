<script setup lang="ts">
import { computed } from 'vue'
import ResumeConflictDialog from '@/components/ResumeConflictDialog.vue'
import TaskConsole from '@/components/TaskConsole.vue'
import IssueBanner from '@/components/IssueBanner.vue'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { useOperationIssue } from '@/composables/selectors/useOperationIssue'
import type { ResumeConflictAction } from '@/types/domain/batch'

const {
  batch,
  pendingConflict,
  canStartBatch,
  cannotStartReason,
  startBatch,
  pauseCurrentTask,
  resumeCurrentTask,
  interruptBatch,
  resolveConflict,
} = useTaskOrchestrator()

const taskIssue = useOperationIssue('task')

const pauseButtonLabel = computed(() => {
  if (batch.controlPending === 'pause') {
    return '暂停中...'
  }
  if (batch.controlPending === 'resume') {
    return '继续中...'
  }
  return batch.phase === 'paused' ? '继续队列' : '暂停队列'
})
const interruptButtonLabel = computed(
  () => batch.phase === 'cancelling' ? '中断中...' : '中断批次',
)

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
        </div>

        <div class="panel-actions">
          <button
            class="primary-button"
            :disabled="!canStartBatch"
            :title="cannotStartReason ?? undefined"
            @click="startBatch()"
          >
            开始队列
          </button>
          <button
            class="ghost-button"
            :disabled="!['running', 'paused'].includes(batch.phase) || batch.controlPending !== null"
            @click="batch.phase === 'paused' ? resumeCurrentTask() : pauseCurrentTask()"
          >
            {{ pauseButtonLabel }}
          </button>
          <button
            class="danger-button"
            :disabled="!['running', 'paused'].includes(batch.phase) || batch.controlPending !== null"
            @click="interruptBatch()"
          >
            {{ interruptButtonLabel }}
          </button>
        </div>
      </div>

      <!-- 启动按钮 disabled 时显式说明原因(未选素材 / 缺输出目录 / etc),
           避免用户对着"灰色按钮"猜测。``cannotStartReason`` 在 useTaskOrchestrator
           单点封装,所有 disabled 文案共享同一来源。 -->
      <p v-if="cannotStartReason" class="start-blocked-hint">{{ cannotStartReason }}</p>

      <IssueBanner :issue="taskIssue" title="任务操作失败" />
    </section>

    <TaskConsole />

    <ResumeConflictDialog
      v-if="pendingConflict"
      :descriptor="pendingConflict"
      @resolve="handleResolveConflict"
    />
  </div>
</template>

<style scoped>
/* 启动按钮 disabled 原因提示。颜色与全局 muted text 一致,
   字号略小,避免视觉抢占主操作。 */
.start-blocked-hint {
  margin: 0.5rem 0 0;
  font-size: 12px;
  color: var(--text-muted, #9ba0a8);
}
</style>
