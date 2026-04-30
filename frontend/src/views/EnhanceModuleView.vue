<script setup lang="ts">
import { computed } from 'vue'
import { RIFE_MODELS } from '@/lib/workflow'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import type { FpsMode, ProcessOrder, TensorBackend, InferenceEngine } from '@/types'

const mediaStore = useMediaStore()
const envStore = useEnvStore()
const presetStore = usePresetStore()

const workflow = computed(() => mediaStore.editor.workflowConfig)
const isPresetMode = computed(() => mediaStore.editingScope === 'preset')
const targetLabel = computed(() =>
  isPresetMode.value ? '默认预设（后续导入会继承）' : `作用于 ${mediaStore.editingSelectionCount} 个文件`,
)
const caption = computed(() =>
  isPresetMode.value
    ? '增强参数可以在导入前先配置好，新导入的视频会直接继承这些默认设置。'
    : '当前修改会同步到激活文件与所有已勾选文件，方便批量套用增强流程。',
)
const interpolationOnnxModels = computed(() => envStore.env.checkResult?.onnx_models?.interpolation ?? [])
const superResolutionOnnxModels = computed(() => envStore.env.checkResult?.onnx_models?.super_resolution ?? [])
const isOnnxBackend = computed(() => workflow.value.interpolation.tensorBackend === 'onnx')

// 根据 GPU vendor 过滤可见后端
const visibleBackends = computed(() => {
  const vendor = envStore.env.checkResult?.gpu?.adapters?.[0]?.vendor
  const support = envStore.env.checkResult?.backend_device_support
  const all: TensorBackend[] = ['pytorch', 'paddle', 'onnx']
  if (!vendor || vendor === 'other' || !support) {
    return all
  }
  // 后端设备支持数据存在时按数据过滤
  const filtered = all.filter((b) => {
    const supported = (support as Record<string, string[]>)[b]
    return supported && supported.length > 0 ? supported.includes(vendor) : true
  })
  if (filtered.length > 0) {
    return filtered
  }
  // 后备推断：数据异常时根据 vendor 硬编码兼容矩阵
  if (vendor === 'hygon') {
    return ['paddle']
  }
  return all
})

// 当前后端支持的推理引擎
const availableEngines = computed(() => {
  const backend = workflow.value.interpolation.tensorBackend
  const engines = envStore.env.checkResult?.tensor_engines?.[backend] ?? []
  if (engines.length > 0) {
    return engines
  }

  // 后备推断：后端未返回 tensor_engines 时根据 GPU 信息推断
  const vendor = envStore.env.checkResult?.gpu?.adapters?.[0]?.vendor
  const cudaAvailable = envStore.env.checkResult?.gpu?.cuda_available
  const gpuAvailable = envStore.env.checkResult?.gpu?.available
  const deviceNames = envStore.env.checkResult?.gpu?.devices ?? []
  const hasNvidiaInName = deviceNames.some((name) => name.toLowerCase().includes('nvidia'))
  // 多种方式判断 NVIDIA GPU：vendor 标签、PyTorch CUDA 检测结果、设备名称
  const isNvidia = vendor === 'nvidia' || cudaAvailable || hasNvidiaInName || (gpuAvailable === true && vendor === undefined)

  if (isNvidia) {
    if (backend === 'pytorch') return ['cuda', 'tensorrt']
    if (backend === 'paddle') return ['cuda', 'tensorrt']
    if (backend === 'onnx') return ['tensorrt', 'cuda']
  }
  if (vendor === 'hygon' && backend === 'paddle') return ['dcu']
  if (vendor === 'hygon') return []
  return ['cuda']
})

// 只要有 GPU 且当前后端有可用的推理引擎，就显示引擎选择器
const showEngineSelector = computed(() => {
  const gpuAvailable = envStore.env.checkResult?.gpu?.available
  return gpuAvailable === true && availableEngines.value.length > 0
})

// 后端显示名称映射
const backendLabels: Record<string, string> = {
  pytorch: 'PyTorch',
  paddle: 'PaddlePaddle',
  onnx: 'ONNX Runtime',
}

// 引擎显示名称映射
const engineLabels: Record<string, string> = {
  cuda: 'CUDA',
  tensorrt: 'TensorRT',
  dcu: 'DCU',
  directml: 'DirectML',
  rocm: 'ROCm',
  cpu: 'CPU',
}

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
      const engines = envStore.env.checkResult?.tensor_engines?.[value] ?? []
      config.interpolation.engine = engines[0] as InferenceEngine
      if (value === 'onnx') {
        config.interpolation.onnxModel ||= interpolationOnnxModels.value[0] ?? ''
        config.superResolution.onnxModel ||= superResolutionOnnxModels.value[0] ?? ''
      }
    })
  },
})

const interpolationEngine = computed({
  get: () => workflow.value.interpolation.engine ?? availableEngines.value[0] ?? 'cuda',
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
              {{ backendLabels[b] }}
            </option>
          </select>
        </label>

        <label v-if="showEngineSelector" class="field">
          <span>推理引擎</span>
          <select v-model="interpolationEngine">
            <option v-for="engine in availableEngines" :key="engine" :value="engine">
              {{ engineLabels[engine] || engine }}
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
