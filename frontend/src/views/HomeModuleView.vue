<script setup lang="ts">
import { useEnvironmentChecker } from '@/composables/app/useEnvironmentChecker'
import { useHomeDashboard } from '@/composables/selectors/useHomeDashboard'
import IssueBanner from '@/components/IssueBanner.vue'

const dashboard = useHomeDashboard()
const { recheckEnvironment } = useEnvironmentChecker()
</script>

<template>
  <div class="module-stack" data-testid="home-module">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>启动探测</h2>
          <p class="panel-caption">应用启动后会优先读取本机缓存的能力探测；只有缓存失效或你手动重新探测时，才会再次执行真实探测。</p>
        </div>

        <div class="panel-actions">
          <span v-if="dashboard.isBootstrapping.value || dashboard.isChecking.value" class="panel-badge">探测中</span>
          <button v-else class="ghost-button" @click="recheckEnvironment()">重新探测</button>
        </div>
      </div>

      <IssueBanner :issue="dashboard.issue.value" title="环境探测失败" />

      <div class="stats-grid stats-grid-4">
        <article v-for="item in dashboard.overviewStats.value" :key="item.label" class="stat-card stat-card-tall">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <div class="chip-row">
        <span class="tag">来源: {{ dashboard.probeSourceLabel.value }}</span>
        <span class="tag">硬件加速: {{ dashboard.checkResult.value?.ffmpeg?.hwaccels?.join(', ') || '--' }}</span>
        <span class="tag">GPU: {{ dashboard.checkResult.value?.gpu?.devices?.join(' / ') || 'CPU only' }}</span>
        <span class="tag">最近真实探测: {{ dashboard.lastProbeAt.value ? new Date(dashboard.lastProbeAt.value).toLocaleString() : '--' }}</span>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码能力</h2>
          <p class="panel-caption">这里展示当前机器真实可用的编码器家族，解码、增强、编码页面会直接复用这些探测结果。</p>
        </div>
      </div>

      <div class="summary-grid">
        <article v-for="item in dashboard.familyCards.value" :key="item.title" class="summary-block">
          <p class="summary-block-title">{{ item.title }}</p>
          <p class="summary-line">{{ item.value }}</p>
        </article>
      </div>
    </section>
  </div>
</template>
