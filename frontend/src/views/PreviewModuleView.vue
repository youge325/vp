<script setup lang="ts">
import { computed } from 'vue'
import TaskConsole from '@/components/TaskConsole.vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const resolvedOutputPath = computed(() => store.task.outputPath || store.output.outputPath)

const previewStats = computed(() => [
  { label: '输出', value: resolvedOutputPath.value || '--' },
  { label: '阶段', value: store.task.stage || '--' },
  { label: '耗时', value: store.task.timeSeconds ? `${store.task.timeSeconds.toFixed(1)} s` : '--' },
  { label: '处理帧数', value: store.task.processedFrames ? `${store.task.processedFrames}` : '--' },
])

function openResolvedOutput() {
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
          <h2>输出与预览</h2>
          <p class="panel-caption">集中查看任务日志、输出路径和结果入口</p>
        </div>

        <div class="panel-actions">
          <button class="ghost-button" :disabled="!resolvedOutputPath" @click="openResolvedOutput()">
            打开文件
          </button>
          <button class="primary-button" :disabled="!resolvedOutputPath" @click="store.openOutputLocation()">
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
    </section>

    <TaskConsole />
  </div>
</template>
