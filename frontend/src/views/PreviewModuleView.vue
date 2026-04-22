<script setup lang="ts">
import { computed } from 'vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const focusItem = computed(() => store.currentTaskItem ?? store.recentCompletedItem ?? store.activeItem)
const resolvedOutputPath = computed(() => focusItem.value?.lastOutputPath || focusItem.value?.taskState.outputPath || '')

const previewStats = computed(() => [
  { label: '文件', value: focusItem.value?.displayName ?? '--' },
  { label: '状态', value: focusItem.value?.taskState.status ?? '--' },
  { label: '耗时', value: focusItem.value?.taskState.timeSeconds ? `${focusItem.value.taskState.timeSeconds.toFixed(1)} s` : '--' },
  { label: '处理帧数', value: focusItem.value?.taskState.processedFrames ? `${focusItem.value.taskState.processedFrames}` : '--' },
])

function openResolvedOutput(): void {
  if (!resolvedOutputPath.value) {
    return
  }
  void store.openFileOrDirectory(resolvedOutputPath.value)
}
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>结果预览</h2>
          <p class="panel-caption">这里聚焦当前执行文件或最近完成文件，便于快速打开结果与查看日志。</p>
        </div>

        <div class="panel-actions">
          <button class="ghost-button" :disabled="!resolvedOutputPath" @click="openResolvedOutput()">打开文件</button>
          <button class="primary-button" :disabled="!resolvedOutputPath" @click="store.openOutputLocation(resolvedOutputPath)">
            打开目录
          </button>
        </div>
      </div>

      <div class="stats-grid stats-grid-4">
        <article v-for="item in previewStats" :key="item.label" class="stat-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <div class="summary-grid">
        <article class="summary-block">
          <p class="summary-block-title">输出路径</p>
          <p class="summary-line">{{ resolvedOutputPath || '尚未生成输出文件' }}</p>
        </article>
        <article class="summary-block">
          <p class="summary-block-title">输出目录</p>
          <p class="summary-line">{{ focusItem?.outputConfig.outputDir || '--' }}</p>
        </article>
      </div>
    </section>

    <TaskConsole />
  </div>
</template>
