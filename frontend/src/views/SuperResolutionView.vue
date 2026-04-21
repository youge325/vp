<script setup lang="ts">
import { onMounted } from 'vue'
import { useWorkbenchStore } from '@/stores/workbench'

const store = useWorkbenchStore()

onMounted(() => {
  store.setPrimaryMode('super_resolution')
})
</script>

<template>
  <div class="section-stack">
    <section class="surface-subpanel section-stack">
      <div class="section-heading">
        <div>
          <p class="summary-title">超分步骤</p>
          <h2>超分辨率与串联顺序</h2>
        </div>
        <label class="switch">
          <input
            v-model="store.workflow.enableSuperResolution"
            type="checkbox"
            @change="store.superResolution.enabled = store.workflow.enableSuperResolution"
          />
          <span>启用超分</span>
        </label>
      </div>

      <div class="form-grid">
        <label class="field">
          <span>超分倍率</span>
          <select v-model.number="store.superResolution.scaleFactor">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>超分算法</span>
          <select v-model="store.superResolution.algorithm">
            <option value="placeholder">placeholder</option>
            <option value="realesrgan-plan">realesrgan-plan</option>
          </select>
        </label>

        <label class="field">
          <span>执行顺序</span>
          <select v-model="store.workflow.processOrder">
            <option value="super_resolution_then_interpolation">先超分后补帧</option>
            <option value="frame_interpolation_then_super_resolution">先补帧后超分</option>
          </select>
        </label>
      </div>
    </section>

    <section class="surface-subpanel section-stack">
      <p class="summary-title">联动说明</p>
      <p class="lead">
        当补帧与超分同时打开时，执行顺序会直接传给 CLI。当前后端仍以占位超分能力为主，但事件流、参数映射和输出链路已经预留好了。
      </p>
    </section>
  </div>
</template>
