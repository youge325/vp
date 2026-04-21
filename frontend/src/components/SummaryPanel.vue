<script setup lang="ts">
import TaskConsole from '@/components/TaskConsole.vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()
</script>

<template>
  <aside class="summary-panel surface-panel">
    <div class="summary-header">
      <div>
        <p class="eyebrow">固定摘要</p>
        <h2>任务侧栏</h2>
      </div>

      <button
        class="ghost-button"
        :disabled="!store.task.outputPath && !store.output.outputPath"
        @click="store.openOutputLocation()"
      >
        打开输出目录
      </button>
    </div>

    <section class="summary-grid">
      <article v-for="section in store.summarySections" :key="section.title" class="summary-card">
        <p class="summary-title">{{ section.title }}</p>
        <p v-for="line in section.lines" :key="line" class="summary-line">{{ line }}</p>
      </article>
    </section>

    <section class="summary-card summary-runtime">
      <p class="summary-title">环境回显</p>
      <p class="summary-line">
        FFmpeg:
        {{ store.env.checkResult?.ffmpeg?.available ? '可用' : '未确认' }}
      </p>
      <p class="summary-line">
        GPU:
        {{
          store.env.checkResult?.gpu?.available
            ? store.env.checkResult?.gpu?.devices?.join(', ')
            : '未检测'
        }}
      </p>
      <p class="summary-line">
        Runtime:
        {{ store.env.checkResult?.runtime?.mode ?? 'workspace/system' }}
      </p>
      <p class="summary-line">
        Model:
        {{ store.env.checkResult?.rife_model?.available ? '默认模型就绪' : '未确认模型' }}
      </p>
    </section>

    <TaskConsole compact />
  </aside>
</template>
