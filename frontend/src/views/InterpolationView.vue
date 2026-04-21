<script setup lang="ts">
import { onMounted } from 'vue'
import { RIFE_MODELS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.setPrimaryMode('frame_interpolation')
})
</script>

<template>
  <div class="section-stack">
    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">补帧流程</p>
          <h2>RIFE 参数、倍速与目标帧率</h2>
        </div>
        <label class="switch">
          <input v-model="store.workflow.enableInterpolation" type="checkbox" />
          <span>启用补帧</span>
        </label>
      </div>

      <div class="form-grid">
        <label class="field">
          <span>Tensor 后端</span>
          <select v-model="store.interpolation.tensorBackend">
            <option value="pytorch">PyTorch</option>
            <option value="paddle">PaddlePaddle</option>
          </select>
        </label>

        <label class="field">
          <span>RIFE 模型</span>
          <select v-model="store.interpolation.model">
            <option v-for="model in RIFE_MODELS" :key="model" :value="model">{{ model }}</option>
          </select>
        </label>

        <label class="field">
          <span>帧率模式</span>
          <select v-model="store.workflow.fpsMode">
            <option value="target">目标帧率</option>
            <option value="multi">补帧倍率</option>
          </select>
        </label>

        <label v-if="store.workflow.fpsMode === 'target'" class="field">
          <span>目标 FPS</span>
          <input v-model.number="store.interpolation.targetFps" type="number" min="24" max="240" />
        </label>

        <label v-else class="field">
          <span>补帧倍率</span>
          <select v-model.number="store.interpolation.multi">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>处理 scale</span>
          <input v-model.number="store.interpolation.scale" type="number" min="0.25" max="1" step="0.05" />
        </label>
      </div>

      <label class="switch">
        <input v-model="store.interpolation.fp16" type="checkbox" />
        <span>启用 FP16（需要显卡支持）</span>
      </label>
    </section>

    <section class="surface-subpanel section-stack">
      <p class="summary-title">当前提示</p>
      <p class="lead">
        {{
          store.source.info
            ? `素材源帧率约 ${store.source.info.fps} fps。当前模式为 ${store.workflow.fpsMode === 'target' ? `目标 ${store.interpolation.targetFps} fps` : `${store.interpolation.multi}x 倍率`}。`
            : '先导入素材，系统会根据输入帧率帮你更好判断补帧收益。'
        }}
      </p>
    </section>
  </div>
</template>
