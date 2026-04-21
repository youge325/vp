<script setup lang="ts">
import { onMounted } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.setPrimaryMode('format_conversion')
})
</script>

<template>
  <div class="section-stack">
    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">格式转换</p>
          <h2>封装、音频和交付容器</h2>
        </div>
      </div>

      <div class="form-grid">
        <label class="switch field">
          <input v-model="store.format.remuxOnly" type="checkbox" />
          <span>仅重封装</span>
        </label>

        <label class="switch field">
          <input v-model="store.format.keepAudio" type="checkbox" />
          <span>保留音频</span>
        </label>

        <label class="field">
          <span>目标容器</span>
          <select v-model="store.format.container">
            <option value="mp4">MP4</option>
            <option value="mkv">MKV</option>
            <option value="mov">MOV</option>
            <option value="webm">WEBM</option>
          </select>
        </label>
      </div>
    </section>

    <section class="surface-subpanel section-stack">
      <p class="summary-title">交付建议</p>
      <p class="lead">
        如果你的目标只是压体积或换编码器，就把重心放在输出与执行页里的 codec、preset 和 CRF。真正的视频增强步骤可以关闭，只保留格式转换链路。
      </p>
    </section>
  </div>
</template>
