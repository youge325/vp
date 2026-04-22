<script setup lang="ts">
import { computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { PROCESS_ORDER_LABELS, RIFE_MODELS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'

const route = useRoute()
const store = useWorkbenchStore()

const enhancementStats = computed(() => [
  { label: '补帧', value: store.workflow.enableInterpolation ? 'On' : 'Off' },
  { label: '超分', value: store.workflow.enableSuperResolution ? 'On' : 'Off' },
  { label: '动漫', value: store.anime.enabled ? 'On' : 'Off' },
  {
    label: '顺序',
    value:
      store.workflow.enableInterpolation && store.workflow.enableSuperResolution
        ? PROCESS_ORDER_LABELS[store.workflow.processOrder]
        : '--',
  },
])

async function scrollToSection(section: string | null) {
  if (!section) {
    return
  }

  await nextTick()
  document.getElementById(section)?.scrollIntoView({ block: 'start', behavior: 'smooth' })
}

onMounted(() => {
  const section = Array.isArray(route.query.section) ? route.query.section[0] : route.query.section
  void scrollToSection(typeof section === 'string' ? section : null)
})

watch(
  () => route.query.section,
  (value) => {
    const section = Array.isArray(value) ? value[0] : value
    void scrollToSection(typeof section === 'string' ? section : null)
  },
)
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>增强总览</h2>
          <p class="panel-caption">保留补帧、超分、动漫三个页内分区</p>
        </div>
        <span class="panel-badge">同一流程</span>
      </div>

      <div class="stats-grid stats-grid-4">
        <article v-for="item in enhancementStats" :key="item.label" class="stat-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </article>
      </div>
    </section>

    <section id="interpolation" class="panel-surface">
      <div class="panel-head">
        <h2>补帧</h2>
        <label class="toggle-chip">
          <input v-model="store.workflow.enableInterpolation" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>后端</span>
          <select v-model="store.interpolation.tensorBackend">
            <option value="pytorch">PyTorch</option>
            <option value="paddle">PaddlePaddle</option>
          </select>
        </label>

        <label class="field">
          <span>模型</span>
          <select v-model="store.interpolation.model">
            <option v-for="model in RIFE_MODELS" :key="model" :value="model">{{ model }}</option>
          </select>
        </label>

        <label class="field">
          <span>帧率模式</span>
          <select v-model="store.workflow.fpsMode">
            <option value="target">目标 FPS</option>
            <option value="multi">倍数</option>
          </select>
        </label>

        <label v-if="store.workflow.fpsMode === 'target'" class="field">
          <span>目标 FPS</span>
          <input v-model.number="store.interpolation.targetFps" type="number" min="24" max="240" />
        </label>

        <label v-else class="field">
          <span>倍数</span>
          <select v-model.number="store.interpolation.multi">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>Scale</span>
          <input v-model.number="store.interpolation.scale" type="number" min="0.25" max="1" step="0.05" />
        </label>

        <label class="field toggle-field">
          <span>精度</span>
          <label class="toggle-chip">
            <input v-model="store.interpolation.fp16" type="checkbox" />
            <span>FP16</span>
          </label>
        </label>
      </div>
    </section>

    <section id="super-resolution" class="panel-surface">
      <div class="panel-head">
        <h2>超分</h2>
        <label class="toggle-chip">
          <input v-model="store.workflow.enableSuperResolution" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>倍率</span>
          <select v-model.number="store.superResolution.scaleFactor">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>算法</span>
          <select v-model="store.superResolution.algorithm">
            <option value="placeholder">placeholder</option>
            <option value="realesrgan-plan">realesrgan-plan</option>
          </select>
        </label>

        <label class="field field-span-2">
          <span>顺序</span>
          <select v-model="store.workflow.processOrder">
            <option value="super_resolution_then_interpolation">先超分后补帧</option>
            <option value="frame_interpolation_then_super_resolution">先补帧后超分</option>
          </select>
        </label>
      </div>
    </section>

    <section id="anime" class="panel-surface">
      <div class="panel-head">
        <h2>动漫</h2>
        <label class="toggle-chip">
          <input v-model="store.anime.enabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-3">
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
          <input v-model.number="store.anime.denoise" type="number" min="0" max="100" />
        </label>

        <label class="field">
          <span>边缘</span>
          <input v-model.number="store.anime.edgeBoost" type="number" min="0" max="100" />
        </label>
      </div>
    </section>
  </div>
</template>
