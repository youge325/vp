<script setup lang="ts">
import { computed } from 'vue'
import { formatNumber } from '@/lib/task-mapper'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

const inputStats = computed(() => [
  {
    label: '文件',
    value: store.source.inputPath ? store.source.inputPath.split(/[/\\]/).pop() ?? store.source.inputPath : '--',
  },
  {
    label: '分辨率',
    value: store.source.info ? `${store.source.info.width} × ${store.source.info.height}` : '--',
  },
  {
    label: '帧率',
    value: store.source.info ? `${formatNumber(store.source.info.fps)} FPS` : '--',
  },
  {
    label: '音频',
    value: store.source.info ? (store.source.info.has_audio ? 'Yes' : 'No') : '--',
  },
])
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>素材输入</h2>
          <p class="panel-caption">选择输入视频并读取媒体信息</p>
        </div>

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
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>素材信息</h2>
          <p class="panel-caption">读取后会同步影响补帧目标帧率和输出推导</p>
        </div>
      </div>

      <div class="stats-grid stats-grid-4">
        <article v-for="item in inputStats" :key="item.label" class="stat-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>
  </div>
</template>
