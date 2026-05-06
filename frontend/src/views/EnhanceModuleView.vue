<script setup lang="ts">
import { computed } from 'vue'
import { RIFE_MODELS } from '@/lib/workflow'
import { useWorkbenchEditor } from '@/composables/useEditor'
import { BACKEND_LABELS, ENGINE_LABELS } from '@/services/format'
import { getVisibleBackends, getAvailableEngines, shouldShowEngineSelector } from '@/services/gpu'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { FpsMode, ProcessOrder, TensorBackend, InferenceEngine } from '@/types'

const envStore = useEnvStore()
const presetStore = usePresetStore()
const { editorConfig, editingScopeLabel } = useWorkbenchEditor()

const workflow = computed(() => editorConfig.value.workflowConfig)
const targetLabel = computed(() => editingScopeLabel.value.targetLabel)
const caption = computed(() => editingScopeLabel.value.caption)
const interpolationOnnxModels = computed(() => envStore.env.checkResult?.onnxModels?.interpolation ?? [])
const superResolutionOnnxModels = computed(() => envStore.env.checkResult?.onnxModels?.super_resolution ?? [])
const isOnnxBackend = computed(() => workflow.value.interpolation.tensorBackend === 'onnx')

const visibleBackends = computed(() => getVisibleBackends(envStore.env.checkResult))

const interpolationEnabled = computed({
  get: () => workflow.value.interpolation.enabled,
  set: (value: boolean) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.enabled = value
    })
  },
})

const interpolationBackend = computed({
  get: () => workflow.value.interpolation.tensorBackend,
  set: (value: TensorBackend) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.tensorBackend = value
      // 自动选择该后端的第一个可用推理引擎
      const engines = envStore.env.checkResult?.tensorEngines?.[value] ?? []
      config.interpolation.engine = engines[0] as InferenceEngine
      if (value === 'onnx') {
        config.interpolation.onnxModel ||= interpolationOnnxModels.value[0] ?? ''
        config.superResolution.onnxModel ||= superResolutionOnnxModels.value[0] ?? ''
      }
    })
  },
})

const interpolationEngine = computed({
  get: () => workflow.value.interpolation.engine ?? getAvailableEngines(envStore.env.checkResult, workflow.value.interpolation.tensorBackend as TensorBackend)[0] ?? 'cuda',
  set: (value: InferenceEngine) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.engine = value
    })
  },
})

const interpolationModel = computed({
  get: () => workflow.value.interpolation.model,
  set: (value: string) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.model = value
    })
  },
})

const interpolationOnnxModel = computed({
  get: () => workflow.value.interpolation.onnxModel ?? '',
  set: (value: string) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.onnxModel = value
    })
  },
})

const fpsMode = computed({
  get: () => workflow.value.fpsMode,
  set: (value: FpsMode) => {
    presetStore.patchWorkflow((config) => {
      config.fpsMode = value
    })
  },
})

const targetFps = computed({
  get: () => workflow.value.interpolation.targetFps,
  set: (value: number) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.targetFps = value
    })
  },
})

const interpolationMulti = computed({
  get: () => workflow.value.interpolation.multi,
  set: (value: number) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.multi = value
    })
  },
})

const interpolationScale = computed({
  get: () => workflow.value.interpolation.scale,
  set: (value: number) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.scale = value
    })
  },
})

const interpolationFp16 = computed({
  get: () => workflow.value.interpolation.fp16,
  set: (value: boolean) => {
    presetStore.patchWorkflow((config) => {
      config.interpolation.fp16 = value
    })
  },
})

const superResolutionEnabled = computed({
  get: () => workflow.value.superResolution.enabled,
  set: (value: boolean) => {
    presetStore.patchWorkflow((config) => {
      config.superResolution.enabled = value
    })
  },
})

const superResolutionScale = computed({
  get: () => workflow.value.superResolution.scaleFactor,
  set: (value: number) => {
    presetStore.patchWorkflow((config) => {
      config.superResolution.scaleFactor = value
    })
  },
})

const superResolutionAlgorithm = computed({
  get: () => workflow.value.superResolution.algorithm,
  set: (value: string) => {
    presetStore.patchWorkflow((config) => {
      config.superResolution.algorithm = value
    })
  },
})

const superResolutionOnnxModel = computed({
  get: () => workflow.value.superResolution.onnxModel ?? '',
  set: (value: string) => {
    presetStore.patchWorkflow((config) => {
      config.superResolution.onnxModel = value
    })
  },
})

const processOrder = computed({
  get: () => workflow.value.processOrder,
  set: (value: ProcessOrder) => {
    presetStore.patchWorkflow((config) => {
      config.processOrder = value
    })
  },
})

const animeEnabled = computed({
  get: () => workflow.value.anime.enabled,
  set: (value: boolean) => {
    presetStore.patchWorkflow((config) => {
      config.anime.enabled = value
    })
  },
})

const animeProfile = computed({
  get: () => workflow.value.anime.profile,
  set: (value: string) => {
    presetStore.patchWorkflow((config) => {
      config.anime.profile = value
    })
  },
})

const animeDenoise = computed({
  get: () => workflow.value.anime.denoise,
  set: (value: number) => {
    presetStore.patchWorkflow((config) => {
      config.anime.denoise = value
    })
  },
})

const animeEdgeBoost = computed({
  get: () => workflow.value.anime.edgeBoost,
  set: (value: number) => {
    presetStore.patchWorkflow((config) => {
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
            <option v-for="b in visibleBackends" :key="b" :value="b">
              {{ BACKEND_LABELS[b] }}
            </option>
          </select>
        </label>

        <label v-if="shouldShowEngineSelector(envStore.env.checkResult, interpolationBackend as TensorBackend)" class="field">
          <span>推理引擎</span>
          <select v-model="interpolationEngine">
            <option v-for="engine in getAvailableEngines(envStore.env.checkResult, interpolationBackend as TensorBackend)" :key="engine" :value="engine">
              {{ ENGINE_LABELS[engine] || engine }}
            </option>
          </select>
        </label>

        <label v-if="!isOnnxBackend" class="field">
          <span>模型</span>
          <select v-model="interpolationModel">
            <option v-for="model in RIFE_MODELS" :key="model" :value="model">{{ model }}</option>
          </select>
        </label>

        <label v-if="isOnnxBackend" class="field">
          <span>ONNX 补帧模型</span>
          <select v-model="interpolationOnnxModel" :disabled="interpolationOnnxModels.length === 0">
            <option value="">未选择</option>
            <option v-for="model in interpolationOnnxModels" :key="model" :value="model">{{ model }}</option>
          </select>
          <span v-if="interpolationOnnxModels.length === 0" class="field-hint">未找到 ONNX 模型，请将 .onnx 文件放入 models/interpolation 目录</span>
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

        <label v-if="isOnnxBackend" class="field">
          <span>ONNX 超分模型</span>
          <select v-model="superResolutionOnnxModel" :disabled="superResolutionOnnxModels.length === 0">
            <option value="">未选择</option>
            <option v-for="model in superResolutionOnnxModels" :key="model" :value="model">{{ model }}</option>
          </select>
          <span v-if="superResolutionOnnxModels.length === 0" class="field-hint">未找到 ONNX 模型，请将 .onnx 文件放入 models/super_resolution 目录</span>
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
