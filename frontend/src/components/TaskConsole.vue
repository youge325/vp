<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

defineProps<{
  compact?: boolean
}>()

const store = useWorkbenchStore()

const headline = computed(() => {
  if (store.task.status === 'running') {
    return `阶段 ${store.task.stageIndex || 1}/${store.task.stageTotal || 1} · ${store.task.stage || '处理中'}`
  }

  if (store.task.status === 'completed') {
    return `输出完成 · ${store.task.processedFrames} 帧 · ${store.task.timeSeconds.toFixed(1)}s`
  }

  if (store.task.status === 'error') {
    return store.task.error?.message ?? '任务失败'
  }

  if (store.task.status === 'cancelled') {
    return '任务已取消'
  }

  return '等待执行'
})
</script>

<template>
  <section class="task-console surface-subpanel" :class="{ compact }">
    <div class="console-head">
      <div>
        <p class="summary-title">执行状态</p>
        <strong>{{ headline }}</strong>
      </div>
      <span class="status-pill" :data-state="store.task.status">{{ store.task.percent.toFixed(1) }}%</span>
    </div>

    <div class="progress-track">
      <span class="progress-fill" :style="{ width: `${store.task.percent}%` }" />
    </div>

    <p class="summary-line">
      {{
        store.task.total
          ? `当前 ${store.task.current} / ${store.task.total}`
          : '运行日志会持续写入这里。'
      }}
    </p>

    <div class="log-panel">
      <p v-if="store.task.logs.length === 0" class="log-line subtle">还没有收到日志输出。</p>
      <p v-for="(line, index) in store.task.logs" :key="`${index}-${line}`" class="log-line">
        {{ line }}
      </p>
    </div>
  </section>
</template>
