<script setup lang="ts">
import { computed } from 'vue'
import { RIFE_MODELS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { FpsMode, ProcessOrder, TensorBackend } from '@/types'

const store = useWorkbenchStore()

const activeWorkflow = computed(() => store.activeItem?.workflowConfig ?? null)

const interpolationEnabled = computed({
  get: () => activeWorkflow.value?.interpolation.enabled ?? false,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.interpolation.enabled = value
    })
  },
})

const interpolationBackend = computed({
  get: () => activeWorkflow.value?.interpolation.tensorBackend ?? 'pytorch',
  set: (value: TensorBackend) => {
    store.patchWorkflow((config) => {
      config.interpolation.tensorBackend = value
    })
  },
})

const interpolationModel = computed({
  get: () => activeWorkflow.value?.interpolation.model ?? '4.25',
  set: (value: string) => {
    store.patchWorkflow((config) => {
      config.interpolation.model = value
    })
  },
})

const fpsMode = computed({
  get: () => activeWorkflow.value?.fpsMode ?? 'target',
  set: (value: FpsMode) => {
    store.patchWorkflow((config) => {
      config.fpsMode = value
    })
  },
})

const targetFps = computed({
  get: () => activeWorkflow.value?.interpolation.targetFps ?? 60,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.interpolation.targetFps = value
    })
  },
})

const interpolationMulti = computed({
  get: () => activeWorkflow.value?.interpolation.multi ?? 2,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.interpolation.multi = value
    })
  },
})

const interpolationScale = computed({
  get: () => activeWorkflow.value?.interpolation.scale ?? 1,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.interpolation.scale = value
    })
  },
})

const interpolationFp16 = computed({
  get: () => activeWorkflow.value?.interpolation.fp16 ?? false,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.interpolation.fp16 = value
    })
  },
})

const superResolutionEnabled = computed({
  get: () => activeWorkflow.value?.superResolution.enabled ?? false,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.superResolution.enabled = value
    })
  },
})

const superResolutionScale = computed({
  get: () => activeWorkflow.value?.superResolution.scaleFactor ?? 2,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.superResolution.scaleFactor = value
    })
  },
})

const superResolutionAlgorithm = computed({
  get: () => activeWorkflow.value?.superResolution.algorithm ?? 'placeholder',
  set: (value: string) => {
    store.patchWorkflow((config) => {
      config.superResolution.algorithm = value
    })
  },
})

const processOrder = computed({
  get: () => activeWorkflow.value?.processOrder ?? 'super_resolution_then_interpolation',
  set: (value: ProcessOrder) => {
    store.patchWorkflow((config) => {
      config.processOrder = value
    })
  },
})

const animeEnabled = computed({
  get: () => activeWorkflow.value?.anime.enabled ?? false,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.anime.enabled = value
    })
  },
})

const animeProfile = computed({
  get: () => activeWorkflow.value?.anime.profile ?? 'clean-lines',
  set: (value: string) => {
    store.patchWorkflow((config) => {
      config.anime.profile = value
    })
  },
})

const animeDenoise = computed({
  get: () => activeWorkflow.value?.anime.denoise ?? 10,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.anime.denoise = value
    })
  },
})

const animeEdgeBoost = computed({
  get: () => activeWorkflow.value?.anime.edgeBoost ?? 15,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.anime.edgeBoost = value
    })
  },
})
</script>

<template>
  <div class="module-stack">
    <section v-if="!store.activeItem" class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>增强流程</h2>
          <p class="panel-caption">增强页始终显示激活文件的表单值，所有修改会同步到激活文件和已勾选文件。</p>
        </div>
      </div>

      <div v-if="!store.activeItem" class="empty-state">
        <strong>还没有激活文件</strong>
        <p>请先在输入页导入并选中至少一个视频。</p>
      </div>
    </section>

    <section v-if="store.activeItem" class="panel-surface">
      <div class="panel-head">
        <h2>补帧</h2>
        <label class="toggle-chip">
          <input v-model="interpolationEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>后端</span>
          <select v-model="interpolationBackend">
            <option value="pytorch">PyTorch</option>
            <option value="paddle">PaddlePaddle</option>
          </select>
        </label>

        <label class="field">
          <span>模型</span>
          <select v-model="interpolationModel">
            <option v-for="model in RIFE_MODELS" :key="model" :value="model">{{ model }}</option>
          </select>
        </label>

        <label class="field">
          <span>帧率模式</span>
          <select v-model="fpsMode">
            <option value="target">目标 FPS</option>
            <option value="multi">倍数</option>
          </select>
        </label>

        <label v-if="fpsMode === 'target'" class="field">
          <span>目标 FPS</span>
          <input v-model.number="targetFps" type="number" min="24" max="240" />
        </label>

        <label v-else class="field">
          <span>倍数</span>
          <select v-model.number="interpolationMulti">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>Scale</span>
          <input v-model.number="interpolationScale" type="number" min="0.25" max="1" step="0.05" />
        </label>

        <label class="field toggle-field">
          <span>精度</span>
          <label class="toggle-chip">
            <input v-model="interpolationFp16" type="checkbox" />
            <span>FP16</span>
          </label>
        </label>
      </div>
    </section>

    <section v-if="store.activeItem" class="panel-surface">
      <div class="panel-head">
        <h2>超分</h2>
        <label class="toggle-chip">
          <input v-model="superResolutionEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>倍率</span>
          <select v-model.number="superResolutionScale">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>算法</span>
          <select v-model="superResolutionAlgorithm">
            <option value="placeholder">placeholder</option>
            <option value="realesrgan-plan">realesrgan-plan</option>
          </select>
        </label>

        <label class="field field-span-2">
          <span>处理顺序</span>
          <select v-model="processOrder">
            <option value="super_resolution_then_interpolation">先超分后补帧</option>
            <option value="frame_interpolation_then_super_resolution">先补帧后超分</option>
          </select>
        </label>
      </div>
    </section>

    <section v-if="store.activeItem" class="panel-surface">
      <div class="panel-head">
        <h2>动漫优化</h2>
        <label class="toggle-chip">
          <input v-model="animeEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-3">
        <label class="field">
          <span>预设</span>
          <select v-model="animeProfile">
            <option value="clean-lines">clean-lines</option>
            <option value="thin-outline">thin-outline</option>
            <option value="balanced-cel">balanced-cel</option>
          </select>
        </label>

        <label class="field">
          <span>降噪</span>
          <input v-model.number="animeDenoise" type="number" min="0" max="100" />
        </label>

        <label class="field">
          <span>边缘增强</span>
          <input v-model.number="animeEdgeBoost" type="number" min="0" max="100" />
        </label>
      </div>
    </section>
  </div>
</template>
