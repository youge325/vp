<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { WORKFLOW_STEPS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'

const route = useRoute()
const store = useWorkbenchStore()

const primaryModeLabel = computed(() => {
  switch (store.workflow.primaryMode) {
    case 'frame_interpolation':
      return '补帧主流程'
    case 'super_resolution':
      return '超分主流程'
    case 'anime_optimization':
      return '动漫优化主流程'
    default:
      return '格式转换主流程'
  }
})
</script>

<template>
  <aside class="step-rail surface-panel">
    <div class="rail-hero">
      <p class="eyebrow">硬替换重构</p>
      <h2>深色工作台</h2>
      <p class="subtle">
        左侧步骤、中央编辑、右侧摘要固定。当前：{{ primaryModeLabel }}
      </p>
    </div>

    <nav class="step-list">
      <RouterLink
        v-for="step in WORKFLOW_STEPS"
        :key="step.key"
        :to="step.path"
        class="step-link"
        :class="{ active: route.path === step.path }"
      >
        <span class="step-index">{{ step.index.toString().padStart(2, '0') }}</span>
        <span>
          <strong>{{ step.title }}</strong>
          <small>{{ step.subtitle }}</small>
        </span>
      </RouterLink>
    </nav>

    <section class="rail-footer">
      <div class="metric-card">
        <span>素材</span>
        <strong>{{ store.source.inputPath ? '已导入' : '待导入' }}</strong>
      </div>
      <div class="metric-card">
        <span>环境</span>
        <strong>{{ store.env.checkResult ? '已检查' : '未检查' }}</strong>
      </div>
      <div class="metric-card">
        <span>输出</span>
        <strong>{{ store.output.outputPath || '自动生成' }}</strong>
      </div>
    </section>
  </aside>
</template>
