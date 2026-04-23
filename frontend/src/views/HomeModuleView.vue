<script setup lang="ts">
import { computed } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const overviewStats = computed(() => [
  { label: '运行时', value: store.env.checkResult?.runtime?.mode ?? '--' },
  { label: 'FFmpeg', value: store.env.checkResult?.ffmpeg?.available ? 'Ready' : 'Missing' },
  { label: '已探测编码器', value: `${store.visibleEncoderProfiles.length}` },
  { label: '已导入素材', value: `${store.mediaItems.length}` },
])

const familyCards = computed(() => {
  const profiles = store.visibleEncoderProfiles
  return [
    {
      title: 'CPU',
      value: profiles.filter((profile) => profile.family === 'cpu').map((profile) => profile.name).join(', ') || '--',
    },
    {
      title: 'NVENC',
      value:
        profiles.filter((profile) => profile.family === 'nvidia').map((profile) => profile.name).join(', ') || '--',
    },
    {
      title: 'QSV',
      value: profiles.filter((profile) => profile.family === 'intel').map((profile) => profile.name).join(', ') || '--',
    },
  ]
})

const probeSourceLabel = computed(() => {
  if (store.env.checkSource === 'cache') {
    return '缓存'
  }
  if (store.env.checkSource === 'probe') {
    return '实时探测'
  }
  return '--'
})
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>启动探测</h2>
          <p class="panel-caption">应用启动后会优先读取本机缓存的能力探测；只有缓存失效或你手动重新探测时，才会再次执行真实探测。</p>
        </div>

        <div class="panel-actions">
          <span v-if="store.env.isBootstrapping || store.env.isChecking" class="panel-badge">探测中</span>
          <button v-else class="ghost-button" @click="store.recheckEnvironment()">重新探测</button>
        </div>
      </div>

      <div v-if="store.env.issue" class="info-banner info-banner-danger">
        <strong>环境探测失败</strong>
        <p>{{ store.env.issue.message }}</p>
      </div>

      <div class="stats-grid stats-grid-4">
        <article v-for="item in overviewStats" :key="item.label" class="stat-card stat-card-tall">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>

      <div class="chip-row">
        <span class="tag">来源: {{ probeSourceLabel }}</span>
        <span class="tag">硬件加速: {{ store.env.checkResult?.ffmpeg?.hwaccels?.join(', ') || '--' }}</span>
        <span class="tag">GPU: {{ store.env.checkResult?.gpu?.devices?.join(' / ') || 'CPU only' }}</span>
        <span class="tag">最近真实探测: {{ store.env.lastProbeAt ? new Date(store.env.lastProbeAt).toLocaleString() : '--' }}</span>
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
        <article v-for="item in familyCards" :key="item.title" class="summary-block">
          <p class="summary-block-title">{{ item.title }}</p>
          <p class="summary-line">{{ item.value }}</p>
        </article>
      </div>
    </section>
  </div>
</template>
