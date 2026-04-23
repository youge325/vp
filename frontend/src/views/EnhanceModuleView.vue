<script setup lang="ts">
import { computed } from 'vue'
import { RIFE_MODELS } from '@/lib/workflow'
import { useWorkbenchStore } from '@/stores/workbench'
import type { FpsMode, ProcessOrder, TensorBackend } from '@/types'

const store = useWorkbenchStore()

const workflow = computed(() => store.editor.workflowConfig)
const isPresetMode = computed(() => store.editingScope === 'preset')
const targetLabel = computed(() =>
  isPresetMode.value ? '默认预设（后续导入会继承）' : `作用于 ${store.editingSelectionCount} 个文件`,
)
const caption = computed(() =>
  isPresetMode.value
    ? '增强参数可以在导入前先配置好，新导入的视频会直接继承这些默认设置。'
    : '当前修改会同步到激活文件与所有已勾选文件，方便批量套用增强流程。',
)

const interpolationEnabled = computed({
  get: () => workflow.value.interpolation.enabled,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.interpolation.enabled = value
    })
  },
})

const interpolationBackend = computed({
  get: () => workflow.value.interpolation.tensorBackend,
  set: (value: TensorBackend) => {
    store.patchWorkflow((config) => {
      config.interpolation.tensorBackend = value
    })
  },
})

const interpolationModel = computed({
  get: () => workflow.value.interpolation.model,
  set: (value: string) => {
    store.patchWorkflow((config) => {
      config.interpolation.model = value
    })
  },
})

const fpsMode = computed({
  get: () => workflow.value.fpsMode,
  set: (value: FpsMode) => {
    store.patchWorkflow((config) => {
      config.fpsMode = value
    })
  },
})

const targetFps = computed({
  get: () => workflow.value.interpolation.targetFps,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.interpolation.targetFps = value
    })
  },
})

const interpolationMulti = computed({
  get: () => workflow.value.interpolation.multi,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.interpolation.multi = value
    })
  },
})

const interpolationScale = computed({
  get: () => workflow.value.interpolation.scale,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.interpolation.scale = value
    })
  },
})

const interpolationFp16 = computed({
  get: () => workflow.value.interpolation.fp16,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.interpolation.fp16 = value
    })
  },
})

const superResolutionEnabled = computed({
  get: () => workflow.value.superResolution.enabled,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.superResolution.enabled = value
    })
  },
})

const superResolutionScale = computed({
  get: () => workflow.value.superResolution.scaleFactor,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.superResolution.scaleFactor = value
    })
  },
})

const superResolutionAlgorithm = computed({
  get: () => workflow.value.superResolution.algorithm,
  set: (value: string) => {
    store.patchWorkflow((config) => {
      config.superResolution.algorithm = value
    })
  },
})

const processOrder = computed({
  get: () => workflow.value.processOrder,
  set: (value: ProcessOrder) => {
    store.patchWorkflow((config) => {
      config.processOrder = value
    })
  },
})

const animeEnabled = computed({
  get: () => workflow.value.anime.enabled,
  set: (value: boolean) => {
    store.patchWorkflow((config) => {
      config.anime.enabled = value
    })
  },
})

const animeProfile = computed({
  get: () => workflow.value.anime.profile,
  set: (value: string) => {
    store.patchWorkflow((config) => {
      config.anime.profile = value
    })
  },
})

const animeDenoise = computed({
  get: () => workflow.value.anime.denoise,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.anime.denoise = value
    })
  },
})

const animeEdgeBoost = computed({
  get: () => workflow.value.anime.edgeBoost,
  set: (value: number) => {
    store.patchWorkflow((config) => {
      config.anime.edgeBoost = value
    })
  },
})
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>增强流程</h2>
          <p class="panel-caption">{{ caption }}</p>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>
    </section>

    <section class="panel-surface">
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
            <option value="multi">倍率</option>
          </select>
        </label>

        <label v-if="fpsMode === 'target'" class="field">
          <span>目标 FPS</span>
          <input v-model.number="targetFps" type="number" min="24" max="240" />
        </label>

        <label v-else class="field">
          <span>倍率</span>
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

    <section class="panel-surface">
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

    <section class="panel-surface">
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
