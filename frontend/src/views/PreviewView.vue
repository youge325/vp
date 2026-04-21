<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const outputPath = computed(() => store.task.outputPath || store.output.outputPath)
</script>

<template>
  <div class="section-stack">
    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">结果预览</p>
          <h2>输出路径、结果回显与定位</h2>
        </div>
        <div class="inline-actions">
          <button class="ghost-button" :disabled="!outputPath" @click="store.openOutputLocation()">
            打开输出目录
          </button>
          <button class="primary-button" :disabled="!outputPath" @click="store.openFileOrDirectory(outputPath || '')">
            打开文件
          </button>
        </div>
      </div>

      <label class="field">
        <span>输出结果</span>
        <textarea :value="outputPath || '任务完成后这里会显示真实输出路径。'" rows="4" readonly />
      </label>
    </section>

    <section class="metrics-grid">
      <article class="metric-tile">
        <span>状态</span>
        <strong>{{ store.task.status }}</strong>
      </article>
      <article class="metric-tile">
        <span>处理帧数</span>
        <strong>{{ store.task.processedFrames || '--' }}</strong>
      </article>
      <article class="metric-tile">
        <span>耗时</span>
        <strong>{{ store.task.timeSeconds ? `${store.task.timeSeconds.toFixed(1)}s` : '--' }}</strong>
      </article>
      <article class="metric-tile">
        <span>错误码</span>
        <strong>{{ store.task.error?.code ?? '--' }}</strong>
      </article>
    </section>

    <section class="surface-subpanel section-stack">
      <p class="summary-title">结果说明</p>
      <p class="lead">
        当前预览页优先保证桌面端可定位输出和回看日志。后续如果要做真正的视频内嵌预览，可以继续接 Tauri 资源协议或本地文件映射。
      </p>
    </section>
  </div>
</template>
