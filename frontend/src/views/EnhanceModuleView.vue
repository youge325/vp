<script setup lang="ts">
import { toRef } from 'vue'
import { useEnhanceForm } from '@/composables/forms/useEnhanceForm'
import { useEditingScope } from '@/composables/selectors/useWorkbenchEditor'
import { useGpuCapabilities } from '@/composables/selectors/useGpuCapabilities'
import { BACKEND_LABELS, ENGINE_LABELS } from '@/config/gpu-labels'

const form = useEnhanceForm()
const { visibleBackends, availableEngines, showEngineSelector } = useGpuCapabilities(
  toRef(form, 'interpolationBackend')
)
const { targetLabel, caption } = useEditingScope('enhance')
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
          <input v-model="form.interpolationEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>后端</span>
          <select v-model="form.interpolationBackend">
            <option v-for="b in visibleBackends" :key="b" :value="b">
              {{ BACKEND_LABELS[b] }}
            </option>
          </select>
        </label>

        <label v-if="showEngineSelector" class="field">
          <span>推理引擎</span>
          <select v-model="form.interpolationEngine">
            <option v-for="engine in availableEngines" :key="engine" :value="engine">
              {{ ENGINE_LABELS[engine] || engine }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>算法</span>
          <select v-model="form.interpolationAlgorithm">
            <option v-for="alg in form.interpolationAlgorithms" :key="alg.name" :value="alg.name">
              {{ alg.name }}
            </option>
          </select>
        </label>

        <label v-if="!form.isOnnxBackend" class="field">
          <span>模型</span>
          <select v-model="form.interpolationModel">
            <option v-for="model in form.interpolationModels" :key="model" :value="model">{{ model }}</option>
          </select>
        </label>

        <label v-if="form.isOnnxBackend" class="field">
          <span>ONNX 补帧模型</span>
          <select v-model="form.interpolationOnnxModel" :disabled="form.interpolationOnnxModels.length === 0">
            <option value="">未选择</option>
            <option v-for="model in form.interpolationOnnxModels" :key="model" :value="model">{{ model }}</option>
          </select>
          <span v-if="form.interpolationOnnxModels.length === 0" class="field-hint">未找到 ONNX 模型，请将 .onnx 文件放入 models/interpolation 目录</span>
        </label>

        <label class="field">
          <span>帧率模式</span>
          <select v-model="form.fpsMode">
            <option value="target">目标 FPS</option>
            <option value="multi">倍率</option>
          </select>
        </label>

        <label v-if="form.fpsMode === 'target'" class="field">
          <span>目标 FPS</span>
          <input v-model.number="form.targetFps" type="number" min="24" max="240" />
        </label>

        <label v-else class="field">
          <span>倍率</span>
          <select v-model.number="form.interpolationMulti">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>Scale</span>
          <input v-model.number="form.interpolationScale" type="number" min="0.25" max="1" step="0.05" />
        </label>

        <label class="field toggle-field">
          <span>精度</span>
          <label class="toggle-chip">
            <input v-model="form.interpolationFp16" type="checkbox" />
            <span>FP16</span>
          </label>
        </label>
      </div>
    </section>

    <section class="panel-surface">
      <div class="panel-head">
        <h2>超分</h2>
        <label class="toggle-chip">
          <input v-model="form.superResolutionEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field">
          <span>倍率</span>
          <select v-model.number="form.superResolutionScale">
            <option :value="2">2x</option>
            <option :value="4">4x</option>
          </select>
        </label>

        <label class="field">
          <span>算法</span>
          <select v-model="form.superResolutionAlgorithm">
            <option
              v-for="alg in form.superResolutionAlgorithms"
              :key="alg.name"
              :value="alg.name"
            >
              {{ alg.name }}
            </option>
          </select>
        </label>

        <label v-if="form.isOnnxBackend" class="field">
          <span>ONNX 超分模型</span>
          <select v-model="form.superResolutionOnnxModel" :disabled="form.superResolutionOnnxModels.length === 0">
            <option value="">未选择</option>
            <option v-for="model in form.superResolutionOnnxModels" :key="model" :value="model">{{ model }}</option>
          </select>
          <span v-if="form.superResolutionOnnxModels.length === 0" class="field-hint">未找到 ONNX 模型，请将 .onnx 文件放入 models/super_resolution 目录</span>
        </label>

        <label class="field field-span-2">
          <span>处理顺序</span>
          <select v-model="form.processOrder">
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
          <input v-model="form.animeEnabled" type="checkbox" />
          <span>启用</span>
        </label>
      </div>

      <div class="field-grid field-grid-3">
        <label class="field">
          <span>预设</span>
          <select v-model="form.animeProfile">
            <option v-for="profile in form.animeProfiles" :key="profile" :value="profile">
              {{ profile }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>降噪</span>
          <input v-model.number="form.animeDenoise" type="number" min="0" max="100" />
        </label>

        <label class="field">
          <span>边缘增强</span>
          <input v-model.number="form.animeEdgeBoost" type="number" min="0" max="100" />
        </label>
      </div>
    </section>
  </div>
</template>
