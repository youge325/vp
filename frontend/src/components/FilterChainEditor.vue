<script setup lang="ts">
import { computed, type Component } from 'vue'
import FilterScale from '@/components/filter-steps/FilterScale.vue'
import FilterCrop from '@/components/filter-steps/FilterCrop.vue'
import FilterPad from '@/components/filter-steps/FilterPad.vue'
import FilterSharpen from '@/components/filter-steps/FilterSharpen.vue'
import FilterDenoise from '@/components/filter-steps/FilterDenoise.vue'
import FilterColor from '@/components/filter-steps/FilterColor.vue'
import type { FilterStep } from '@/types/protocol'
import type { FilterStepKind } from '@/types/domain/workflow'

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

const KIND_COMPONENT: Record<FilterStepKind, Component> = {
  scale: FilterScale,
  crop: FilterCrop,
  pad: FilterPad,
  sharpen: FilterSharpen,
  denoise: FilterDenoise,
  color: FilterColor,
}

const KIND_DEFAULTS: Record<FilterStepKind, Record<string, unknown>> = {
  scale: { mode: 'factor', factor: 0.5, width: 1920, height: 1080, interpolation: 'lanczos4' },
  crop: { x: 0, y: 0, width: 1920, height: 1080 },
  pad: { top: 0, bottom: 0, left: 0, right: 0, color: '#000000' },
  sharpen: { amount: 0.5 },
  denoise: { strength: 10, colorStrength: 10 },
  color: { brightness: 0, contrast: 1, saturation: 1 },
}

function addFilter(kind: FilterStepKind) {
  if (!kind) return
  filters.value = [
    ...filters.value,
    { kind, enabled: true, params: { ...KIND_DEFAULTS[kind] } },
  ]
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

function updateStep(index: number, value: FilterStep) {
  const next = [...filters.value]
  next[index] = value
  filters.value = next
}

function setEnabled(index: number, enabled: boolean) {
  updateStep(index, { ...filters.value[index], enabled })
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
              @change="setEnabled(index, ($event.target as HTMLInputElement).checked)"
            />
            <span>启用</span>
          </label>
          <button type="button" :disabled="index === 0" @click="moveFilter(index, -1)">↑</button>
          <button type="button" :disabled="index === filters.length - 1" @click="moveFilter(index, 1)">↓</button>
          <button type="button" class="filter-delete" @click="removeFilter(index)">删除</button>
        </div>
      </div>

      <div class="filter-card-body">
        <component
          :is="KIND_COMPONENT[step.kind as FilterStepKind]"
          :model-value="step"
          @update:model-value="updateStep(index, $event)"
        />
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
