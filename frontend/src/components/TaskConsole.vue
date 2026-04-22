<script setup lang="ts">
import { computed } from 'vue'
import { createIdleTaskState } from '@/lib/task-events'
import { useWorkbenchStore } from '@/stores/workbench'

defineProps<{
  compact?: boolean
}>()

const store = useWorkbenchStore()

const fallbackTask = createIdleTaskState()

const taskItem = computed(() => store.consoleTaskItem)
const task = computed(() => taskItem.value?.taskState ?? fallbackTask)

const headline = computed(() => {
  if (task.value.status === 'running') {
    const stageIndex = task.value.stageIndex || 1
    const stageTotal = task.value.stageTotal || 1
    return `阶段 ${stageIndex}/${stageTotal} · ${task.value.stage || '处理中'}`
  }

  if (task.value.status === 'completed') {
    return `完成 · ${task.value.processedFrames || 0} 帧`
  }

  if (task.value.status === 'error') {
    return task.value.error?.message ?? '任务失败'
  }

  if (task.value.status === 'cancelled') {
    return '当前项已取消'
  }

  return '等待开始'
})

const fileLabel = computed(() => taskItem.value?.displayName ?? '未选中文件')
</script>

<template>
  <section class="task-console surface-subpanel">
    <div class="task-console-head">
      <div>
        <p class="summary-block-title">CLI</p>
        <strong>{{ headline }}</strong>
        <p class="summary-line">{{ fileLabel }}</p>
      </div>

      <div class="task-console-meta">
        <span>{{ task.percent.toFixed(1) }}%</span>
        <span>{{ task.current || 0 }}/{{ task.total || 0 }}</span>
      </div>
    </div>

    <div class="progress-track">
      <span class="progress-fill" :style="{ width: `${task.percent}%` }" />
    </div>

    <div class="log-panel log-panel-terminal">
      <p v-if="task.logs.length === 0" class="log-line muted-line">$ 等待输出...</p>
      <p v-for="(line, index) in task.logs" :key="`${index}-${line}`" class="log-line">
        {{ line }}
      </p>
    </div>
  </section>
</template>
