<script setup lang="ts">
import { computed } from 'vue'
import type { FilterStep, FilterStepKind } from '@/types'

const props = defineProps<{
  modelValue: FilterStep[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: FilterStep[]): void
}>()

const filters = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const KIND_OPTIONS: { value: FilterStepKind; label: string }[] = [
  { value: 'scale', label: '缩放' },
  { value: 'crop', label: '裁剪' },
  { value: 'pad', label: '填充' },
  { value: 'sharpen', label: '锐化' },
  { value: 'denoise', label: '降噪' },
  { value: 'color', label: '色彩调整' },
]

const INTERP_OPTIONS = [
  { value: 'lanczos4', label: 'Lanczos4' },
  { value: 'cubic', label: 'Cubic' },
  { value: 'area', label: 'Area' },
  { value: 'linear', label: 'Linear' },
]

function addFilter(kind: FilterStepKind) {
  const base: FilterStep = { kind, enabled: true, params: {} }
  switch (kind) {
    case 'scale':
      base.params = { mode: 'factor', factor: 0.5, width: 1920, height: 1080, interpolation: 'lanczos4' }
      break
    case 'crop':
      base.params = { x: 0, y: 0, width: 1920, height: 1080 }
      break
    case 'pad':
      base.params = { top: 0, bottom: 0, left: 0, right: 0, color: '#000000' }
      break
    case 'sharpen':
      base.params = { amount: 0.5 }
      break
    case 'denoise':
      base.params = { strength: 10, colorStrength: 10 }
      break
    case 'color':
      base.params = { brightness: 0, contrast: 1, saturation: 1 }
      break
  }
  filters.value = [...filters.value, base]
}

function removeFilter(index: number) {
  const next = [...filters.value]
  next.splice(index, 1)
  filters.value = next
}

function moveFilter(index: number, direction: number) {
  const next = [...filters.value]
  const newIndex = index + direction
  if (newIndex < 0 || newIndex >= next.length) return
  const [item] = next.splice(index, 1)
  next.splice(newIndex, 0, item)
  filters.value = next
}

function patchFilter(index: number, mutator: (step: FilterStep) => void) {
  const next = [...filters.value]
  const copy = { ...next[index], params: { ...next[index].params } }
  mutator(copy)
  next[index] = copy
  filters.value = next
}

function filterLabel(kind: string) {
  return KIND_OPTIONS.find((k) => k.value === kind)?.label ?? kind
}
</script>

<template>
  <div class="filter-chain-editor">
    <div class="filter-toolbar">
      <select @change="addFilter(($event.target as HTMLSelectElement).value as FilterStepKind)">
        <option value="" disabled selected>+ 添加滤镜</option>
        <option v-for="opt in KIND_OPTIONS" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
    </div>

    <div v-if="filters.length === 0" class="filter-empty">
      <p>尚未添加任何滤镜，请从上方下拉菜单选择。</p>
    </div>

    <div v-for="(step, index) in filters" :key="index" class="filter-card" :data-enabled="step.enabled">
      <div class="filter-card-head">
        <span class="filter-kind">{{ filterLabel(step.kind) }}</span>
        <div class="filter-actions">
          <label class="toggle-chip">
            <input
              :checked="step.enabled"
              type="checkbox"
              @change="patchFilter(index, (s) => (s.enabled = ($event.target as HTMLInputElement).checked))"
            />
            <span>启用</span>
          </label>
          <button type="button" :disabled="index === 0" @click="moveFilter(index, -1)">↑</button>
          <button type="button" :disabled="index === filters.length - 1" @click="moveFilter(index, 1)">↓</button>
          <button type="button" class="filter-delete" @click="removeFilter(index)">删除</button>
        </div>
      </div>

      <div class="filter-card-body">
        <!-- Scale -->
        <template v-if="step.kind === 'scale'">
          <div class="field-grid field-grid-2">
            <label class="field">
              <span>模式</span>
              <select
                :value="step.params.mode ?? 'factor'"
                @change="patchFilter(index, (s) => (s.params.mode = ($event.target as HTMLSelectElement).value))"
              >
                <option value="factor">缩放系数</option>
                <option value="resolution">目标分辨率</option>
              </select>
            </label>
            <label class="field">
              <span>插值算法</span>
              <select
                :value="step.params.interpolation ?? 'lanczos4'"
                @change="patchFilter(index, (s) => (s.params.interpolation = ($event.target as HTMLSelectElement).value))"
              >
                <option v-for="opt in INTERP_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </label>
            <label v-if="step.params.mode === 'resolution'" class="field">
              <span>宽度</span>
              <input
                :value="Number(step.params.width ?? 1920)"
                type="number"
                min="1"
                @input="patchFilter(index, (s) => (s.params.width = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label v-if="step.params.mode === 'resolution'" class="field">
              <span>高度</span>
              <input
                :value="Number(step.params.height ?? 1080)"
                type="number"
                min="1"
                @input="patchFilter(index, (s) => (s.params.height = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label v-if="step.params.mode !== 'resolution'" class="field">
              <span>缩放系数</span>
              <input
                :value="Number(step.params.factor ?? 0.5)"
                type="number"
                step="0.01"
                min="0.01"
                max="10"
                @input="patchFilter(index, (s) => (s.params.factor = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
          </div>
        </template>

        <!-- Crop -->
        <template v-if="step.kind === 'crop'">
          <div class="field-grid field-grid-4">
            <label class="field">
              <span>X</span>
              <input
                :value="Number(step.params.x ?? 0)"
                type="number"
                min="0"
                @input="patchFilter(index, (s) => (s.params.x = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>Y</span>
              <input
                :value="Number(step.params.y ?? 0)"
                type="number"
                min="0"
                @input="patchFilter(index, (s) => (s.params.y = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>宽度</span>
              <input
                :value="Number(step.params.width ?? 1920)"
                type="number"
                min="1"
                @input="patchFilter(index, (s) => (s.params.width = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>高度</span>
              <input
                :value="Number(step.params.height ?? 1080)"
                type="number"
                min="1"
                @input="patchFilter(index, (s) => (s.params.height = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
          </div>
        </template>

        <!-- Pad -->
        <template v-if="step.kind === 'pad'">
          <div class="field-grid field-grid-3">
            <label class="field">
              <span>上</span>
              <input
                :value="Number(step.params.top ?? 0)"
                type="number"
                min="0"
                @input="patchFilter(index, (s) => (s.params.top = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>下</span>
              <input
                :value="Number(step.params.bottom ?? 0)"
                type="number"
                min="0"
                @input="patchFilter(index, (s) => (s.params.bottom = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>左</span>
              <input
                :value="Number(step.params.left ?? 0)"
                type="number"
                min="0"
                @input="patchFilter(index, (s) => (s.params.left = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>右</span>
              <input
                :value="Number(step.params.right ?? 0)"
                type="number"
                min="0"
                @input="patchFilter(index, (s) => (s.params.right = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>颜色 (hex)</span>
              <input
                :value="String(step.params.color ?? '#000000')"
                type="text"
                @input="patchFilter(index, (s) => (s.params.color = ($event.target as HTMLInputElement).value))"
              />
            </label>
          </div>
        </template>

        <!-- Sharpen -->
        <template v-if="step.kind === 'sharpen'">
          <div class="field-grid field-grid-2">
            <label class="field">
              <span>强度 (0~1)</span>
              <input
                :value="Number(step.params.amount ?? 0.5)"
                type="number"
                step="0.05"
                min="0"
                max="1"
                @input="patchFilter(index, (s) => (s.params.amount = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
          </div>
        </template>

        <!-- Denoise -->
        <template v-if="step.kind === 'denoise'">
          <div class="field-grid field-grid-2">
            <label class="field">
              <span>强度 (1~20)</span>
              <input
                :value="Number(step.params.strength ?? 10)"
                type="number"
                min="1"
                max="20"
                @input="patchFilter(index, (s) => (s.params.strength = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>色彩强度 (1~20)</span>
              <input
                :value="Number(step.params.colorStrength ?? 10)"
                type="number"
                min="1"
                max="20"
                @input="patchFilter(index, (s) => (s.params.colorStrength = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
          </div>
        </template>

        <!-- Color -->
        <template v-if="step.kind === 'color'">
          <div class="field-grid field-grid-3">
            <label class="field">
              <span>亮度 (-1~1)</span>
              <input
                :value="Number(step.params.brightness ?? 0)"
                type="number"
                step="0.05"
                min="-1"
                max="1"
                @input="patchFilter(index, (s) => (s.params.brightness = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>对比度 (0~3)</span>
              <input
                :value="Number(step.params.contrast ?? 1)"
                type="number"
                step="0.05"
                min="0"
                max="3"
                @input="patchFilter(index, (s) => (s.params.contrast = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
            <label class="field">
              <span>饱和度 (0~3)</span>
              <input
                :value="Number(step.params.saturation ?? 1)"
                type="number"
                step="0.05"
                min="0"
                max="3"
                @input="patchFilter(index, (s) => (s.params.saturation = Number(($event.target as HTMLInputElement).value)))"
              />
            </label>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.filter-chain-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-toolbar {
  display: flex;
  justify-content: flex-end;
}

.filter-toolbar select {
  width: auto;
  cursor: pointer;
}

.filter-empty {
  padding: 24px;
  text-align: center;
  color: var(--text-3);
  font-size: 14px;
}

.filter-card {
  border: 1px solid var(--surface-3);
  border-radius: 8px;
  background: var(--surface-1);
  overflow: hidden;
}

.filter-card[data-enabled='false'] {
  opacity: 0.6;
}

.filter-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--surface-3);
}

.filter-kind {
  font-weight: 600;
  font-size: 14px;
}

.filter-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-actions button {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--surface-3);
  background: var(--surface-1);
  color: var(--text-1);
  font-size: 13px;
  cursor: pointer;
}

.filter-actions button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.filter-delete {
  color: var(--danger, #ef4444) !important;
}

.filter-card-body {
  padding: 14px;
}
</style>
