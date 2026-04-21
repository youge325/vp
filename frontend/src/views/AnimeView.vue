<script setup lang="ts">
import { onMounted } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.setPrimaryMode('anime_optimization')
})
</script>

<template>
  <div class="section-stack">
    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">动漫优化</p>
          <h2>针对二次元内容的预设区</h2>
        </div>
        <label class="switch">
          <input v-model="store.anime.enabled" type="checkbox" />
          <span>启用动漫优化预设</span>
        </label>
      </div>

      <div class="form-grid">
        <label class="field">
          <span>预设</span>
          <select v-model="store.anime.profile">
            <option value="clean-lines">clean-lines</option>
            <option value="thin-outline">thin-outline</option>
            <option value="balanced-cel">balanced-cel</option>
          </select>
        </label>

        <label class="field">
          <span>降噪</span>
          <input v-model.number="store.anime.denoise" type="range" min="0" max="100" />
        </label>

        <label class="field">
          <span>边缘增强</span>
          <input v-model.number="store.anime.edgeBoost" type="range" min="0" max="100" />
        </label>
      </div>
    </section>

    <section class="surface-subpanel section-stack">
      <p class="summary-title">阶段说明</p>
      <p class="lead">
        第一阶段先保留动漫优化独立页面和状态模型，方便后续挂接真实算法。当前建议把它当作“二次元内容专属交付区”，先做短片段试跑再决定整段处理。
      </p>
    </section>
  </div>
</template>
