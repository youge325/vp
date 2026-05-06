<script setup lang="ts">
import { computed } from 'vue'
import FilterChainEditor from '@/components/FilterChainEditor.vue'
import { useWorkbenchEditor } from '@/composables/useEditor'
import { usePresetStore } from '@/stores/preset'

const presetStore = usePresetStore()
const { editorConfig, editingScopeLabel, isPresetMode } = useWorkbenchEditor()

const workflow = computed(() => editorConfig.value.workflowConfig)
const targetLabel = computed(() => editingScopeLabel.value.targetLabel)
const caption = computed(() =>
  isPresetMode.value
    ? '后处理滤镜链会在增强之后、编码之前执行，可用来锐化、降噪或缩放到目标分辨率。'
    : '当前修改会同步到激活文件与所有已勾选文件。',
)

const postprocessEnabled = computed({
  get: () => workflow.value.postprocess.enabled,
  set: (value: boolean) => {
    presetStore.patchWorkflow((config) => {
      config.postprocess.enabled = value
    })
  },
})

const postprocessFilters = computed({
  get: () => workflow.value.postprocess.filters,
  set: (value) => {
    presetStore.patchWorkflow((config) => {
      config.postprocess.filters = value
    })
  },
})
</script>

<template>
  <div class="module-stack">
    <section class="panel-surface">
      <div class="panel-head">
        <div class="panel-copy">
          <h2>后处理</h2>
          <p class="panel-caption">{{ caption }}</p>
        </div>
        <span class="panel-badge">{{ targetLabel }}</span>
      </div>

      <div class="field-grid field-grid-2">
        <label class="field toggle-field">
          <span>启用后处理</span>
          <label class="toggle-chip">
            <input v-model="postprocessEnabled" type="checkbox" />
            <span>启用</span>
          </label>
        </label>
      </div>

      <div v-if="postprocessEnabled" class="filter-section">
        <p class="panel-caption">位于 增强 → 编码 之间</p>
        <FilterChainEditor v-model="postprocessFilters" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.filter-section {
  margin-top: 16px;
}
</style>
