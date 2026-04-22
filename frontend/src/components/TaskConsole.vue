<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

defineProps<{
  compact?: boolean
}>()

const store = useWorkbenchStore()

const headline = computed(() => {
  if (store.task.status === 'running') {
    const stageIndex = store.task.stageIndex || 1
    const stageTotal = store.task.stageTotal || 1
    return `阶段 ${stageIndex}/${stageTotal} · ${store.task.stage || '处理中'}`
  }

  if (store.task.status === 'completed') {
    return `完成 · ${store.task.processedFrames || 0} 帧`
  }

  if (store.task.status === 'error') {
    return store.task.error?.message ?? '任务失败'
  }

  if (store.task.status === 'cancelled') {
    return '已取消'
  }

  return '等待启动'
})
</script>

<template>
  <section class="task-console surface-subpanel">
    <div class="task-console-head">
      <div>
        <p class="summary-block-title">CLI</p>
        <strong>{{ headline }}</strong>
      </div>

      <div class="task-console-meta">
        <span>{{ store.task.percent.toFixed(1) }}%</span>
        <span>{{ store.task.current || 0 }}/{{ store.task.total || 0 }}</span>
      </div>
    </div>

    <div class="progress-track">
      <span class="progress-fill" :style="{ width: `${store.task.percent}%` }" />
    </div>

    <div class="log-panel log-panel-terminal">
      <p v-if="store.task.logs.length === 0" class="log-line muted-line">$ 等待输出...</p>
      <p v-for="(line, index) in store.task.logs" :key="`${index}-${line}`" class="log-line">
        {{ line }}
      </p>
    </div>
  </section>
</template>
