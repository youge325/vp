<script setup lang="ts">
import { computed } from 'vue'
import FilterChainEditor from '@/components/FilterChainEditor.vue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'

const mediaStore = useMediaStore()
const presetStore = usePresetStore()

const workflow = computed(() => mediaStore.editor.workflowConfig)
const isPresetMode = computed(() => mediaStore.editingScope === 'preset')
const targetLabel = computed(() =>
  isPresetMode.value ? '默认预设（后续导入会继承）' : `作用于 ${mediaStore.editingSelectionCount} 个文件`,
)
const caption = computed(() =>
  isPresetMode.value
    ? '预处理滤镜链会在解码之后、增强之前执行，可用来缩放帧尺寸等。'
    : '当前修改会同步到激活文件与所有已勾选文件。',
)

const preprocessEnabled = computed({
  get: () => workflow.value.preprocess.enabled,
  set: (value: boolean) => {
    presetStore.patchWorkflow((config) => {
      config.preprocess.enabled = value
    })
  },
})

const preprocessFilters = computed({
  get: () => workflow.value.preprocess.filters,
  set: (value) => {
    presetStore.patchWorkflow((config) => {
      config.preprocess.filters = value
    })
  },
})
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>预处理</h2>
          <p class="panel-caption">{{ caption }}</p>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field toggle-field">
          <span>启用预处理</span>
          <label class="toggle-chip">
            <input v-model="preprocessEnabled" type="checkbox" />
            <span>启用</span>
          </label>
        </label>
      </div>

      <div v-if="preprocessEnabled" class="filter-section">
        <p class="panel-caption">位于 解码 → 增强 之间</p>
        <FilterChainEditor v-model="preprocessFilters" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.filter-section {
  margin-top: 16px;
}
</style>
