<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StageTabs from '@/components/StageTabs.vue'
import { PREPARE_TABS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'

type PrepareTab = 'environment' | 'input'

const route = useRoute()
const router = useRouter()
const store = useWorkbenchStore()

function resolveTab(value: unknown): PrepareTab {
  const raw = Array.isArray(value) ? value[0] : value
  return raw === 'input' ? 'input' : 'environment'
}

const activeTab = computed<PrepareTab>(() => resolveTab(route.query.tab))

const activeTabValue = computed({
  get: () => activeTab.value,
  set: (value: string) => {
    const next = resolveTab(value)
    void router.replace({
      path: '/prepare',
      query: next === 'environment' ? {} : { tab: next },
    })
  },
})

const environmentStats = computed(() => [
  { label: 'Runtime', value: store.env.checkResult?.runtime?.mode ?? '--' },
  { label: 'FFmpeg', value: store.env.checkResult?.ffmpeg?.available ? 'Ready' : '--' },
  { label: 'GPU', value: store.env.checkResult?.gpu?.devices?.[0] ?? '--' },
  { label: 'Model', value: store.env.checkResult?.rife_model?.available ? 'Ready' : '--' },
])

const inputStats = computed(() => [
  {
    label: '文件',
    value: store.source.inputPath ? store.source.inputPath.split(/[/\\]/).pop() ?? store.source.inputPath : '--',
  },
  {
    label: '信息',
    value: store.source.info ? 'Ready' : 'Idle',
  },
])
</script>

<template>
  <div class="stage-stack">
    <section class="panel-surface stage-toolbar-panel">
      <StageTabs v-model="activeTabValue" :items="PREPARE_TABS" />
    </section>

    <template v-if="activeTab === 'environment'">
      <section class="panel-surface">
        <div class="panel-head">
          <h2>环境检查</h2>
          <button class="primary-button" :disabled="store.env.isChecking" @click="store.checkEnvironment()">
            {{ store.env.isChecking ? '检查中' : '检查环境' }}
          </button>
        </div>

        <div class="stats-grid stats-grid-4">
          <article v-for="item in environmentStats" :key="item.label" class="stat-card stat-card-tall">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </section>
    </template>

    <template v-else>
      <section class="panel-surface">
        <div class="panel-head">
          <h2>输入</h2>
          <div class="panel-actions">
            <button class="ghost-button" @click="store.pickInput()">选择输入</button>
            <button
              class="primary-button"
              :disabled="!store.source.inputPath || store.source.inspecting"
              @click="store.inspectVideo()"
            >
              {{ store.source.inspecting ? '读取中' : '读取信息' }}
            </button>
          </div>
        </div>

        <div class="field-grid field-grid-1">
          <label class="field">
            <span>输入路径</span>
            <input v-model="store.source.inputPath" type="text" placeholder="选择视频文件或输入路径" />
          </label>
        </div>

        <div class="stats-grid stats-grid-2">
          <article v-for="item in inputStats" :key="item.label" class="stat-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </section>
    </template>
  </div>
</template>
