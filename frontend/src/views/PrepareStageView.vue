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
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>启动探测</h2>
          <p class="panel-caption">应用启动后会自动检查环境，并根据 FFmpeg 与显卡能力动态提供编解码选项。</p>
        </div>

        <div class="panel-actions">
          <span v-if="store.env.isBootstrapping || store.env.isChecking" class="panel-badge">探测中</span>
          <button
            v-else-if="store.env.issue"
            class="ghost-button"
            @click="store.recheckEnvironment()"
          >
            重试探测
          </button>
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
        <span class="tag">硬件加速: {{ store.env.checkResult?.ffmpeg?.hwaccels?.join(', ') || '--' }}</span>
        <span class="tag">GPU: {{ store.env.checkResult?.gpu?.devices?.join(' / ') || 'CPU only' }}</span>
        <span class="tag">最近探测: {{ store.env.lastCheckedAt ? new Date(store.env.lastCheckedAt).toLocaleString() : '--' }}</span>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>编码能力</h2>
          <p class="panel-caption">这里展示的是已经探测到、且当前机器实际可用的编码器家族。</p>
        </div>
      </div>

      <div class="summary-grid">
        <article v-for="item in familyCards" :key="item.title" class="summary-block">
          <p class="summary-block-title">{{ item.title }}</p>
          <p class="summary-line">{{ item.value }}</p>
        </article>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>当前激活文件</h2>
          <p class="panel-caption">主页不再负责选材，只展示当前选中文件的流程摘要。</p>
        </div>
      </div>

      <div class="summary-grid">
        <article v-for="section in store.summarySections" :key="section.title" class="summary-block">
          <p class="summary-block-title">{{ section.title }}</p>
          <p v-for="line in section.lines" :key="line" class="summary-line">{{ line }}</p>
        </article>
      </div>
    </section>
  </div>
</template>
