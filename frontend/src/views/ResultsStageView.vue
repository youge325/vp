<script setup lang="ts">
import { computed } from 'vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const taskOperationIssue = computed(() =>
  store.operationIssue?.scope === 'task' ? store.operationIssue.error : null,
)
const runStats = computed(() => [
  { label: '待处理', value: `${store.selectedIds.length}` },
  { label: '已完成', value: `${store.batch.completedIds.length}` },
  { label: '失败/取消', value: `${store.batch.failedIds.length}` },
  { label: '当前项', value: store.currentTaskItem?.displayName ?? '--' },
])

const queueItems = computed(() =>
  store.mediaItems.filter((item) => item.selected || item.id === store.batch.currentId),
)
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>批处理队列</h2>
          <p class="panel-caption">渲染页只执行当前勾选的文件。任务按固定顺序串行运行，取消当前项后会继续下一项。</p>
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

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>队列明细</h2>
          <p class="panel-caption">可以在这里看到每个已选文件的执行状态、输出结果和最近阶段。</p>
        </div>
      </div>

      <div v-if="queueItems.length === 0" class="empty-state">
        <strong>没有可执行的文件</strong>
        <p>请先在输入页勾选需要进入批处理队列的文件。</p>
      </div>

      <div v-else class="queue-list">
        <article
          v-for="item in queueItems"
          :key="item.id"
          class="queue-card"
          :class="{ active: item.id === store.batch.currentId }"
        >
          <div class="queue-card-head">
            <div>
              <strong>{{ item.displayName }}</strong>
              <p class="summary-line">{{ item.taskState.stage || '等待执行' }}</p>
            </div>
            <span class="inline-status" :data-state="item.taskState.status">{{ item.taskState.status }}</span>
          </div>

          <div class="metric-row">
            <span>{{ item.taskState.percent.toFixed(1) }}%</span>
            <span>{{ item.taskState.current || 0 }}/{{ item.taskState.total || 0 }}</span>
            <span>{{ item.lastOutputPath || '--' }}</span>
          </div>
        </article>
      </div>
    </section>

    <TaskConsole />
  </div>
</template>
