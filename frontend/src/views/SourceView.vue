<script setup lang="ts">
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()
</script>

<template>
  <div class="section-stack">
    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">素材导入</p>
          <h2>输入视频与基础信息</h2>
        </div>
        <div class="inline-actions">
          <button class="primary-button" @click="store.pickInput()">选择文件</button>
          <button class="ghost-button" :disabled="!store.source.inputPath" @click="store.inspectVideo()">
            {{ store.source.inspecting ? '读取中…' : '读取信息' }}
          </button>
        </div>
      </div>

      <label class="field">
        <span>输入路径</span>
        <input v-model="store.source.inputPath" type="text" placeholder="选择一个视频文件" />
      </label>
    </section>

    <section class="metrics-grid">
      <article class="metric-tile">
        <span>FPS</span>
        <strong>{{ store.source.info?.fps ?? '--' }}</strong>
      </article>
      <article class="metric-tile">
        <span>总帧数</span>
        <strong>{{ store.source.info?.frames ?? '--' }}</strong>
      </article>
      <article class="metric-tile">
        <span>时长</span>
        <strong>{{ store.source.info?.duration?.toFixed(1) ?? '--' }}s</strong>
      </article>
      <article class="metric-tile">
        <span>分辨率</span>
        <strong>
          {{
            store.source.info
              ? `${store.source.info.width} × ${store.source.info.height}`
              : '--'
          }}
        </strong>
      </article>
      <article class="metric-tile">
        <span>音频</span>
        <strong>{{ store.source.info?.has_audio ? '有音频' : '未确认' }}</strong>
      </article>
    </section>

    <section class="surface-subpanel section-stack">
      <p class="summary-title">建议</p>
      <p class="lead">
        先把素材信息读出来，再决定目标帧率和是否联动超分。4K 素材建议在补帧时考虑把 scale 降到 0.5，并按显存情况决定是否开启 FP16。
      </p>
    </section>
  </div>
</template>
