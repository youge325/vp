// 视图选择器 — Workbench 编辑器双轨视图(激活素材 vs 默认预设)。
// 保持原 useEditor 的语义,但把它放进 selectors/ 命名空间。

import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { getEditingScopeLabel } from '@/services/format/labels'

export function useWorkbenchEditor() {
  const mediaStore = useMediaStore()
  const presetStore = usePresetStore()

  const activeItem = computed(() => mediaStore.activeItem)
  const isPresetMode = computed(() => !activeItem.value)

  const editorConfig = computed(() => ({
    decodeConfig: activeItem.value?.decodeConfig ?? presetStore.draftPreset.decodeConfig,
    workflowConfig: activeItem.value?.workflowConfig ?? presetStore.draftPreset.workflowConfig,
    encodeConfig: activeItem.value?.encodeConfig ?? presetStore.draftPreset.encodeConfig,
    outputConfig: activeItem.value?.outputConfig ?? presetStore.draftPreset.outputConfig,
  }))

  const editorVideoCodec = computed(() => activeItem.value?.info?.videoCodec ?? '')

  const editingScopeLabel = computed(() =>
    getEditingScopeLabel(isPresetMode.value, mediaStore.selectedIds.length || 1),
  )

  return {
    activeItem,
    isPresetMode,
    editorConfig,
    editorVideoCodec,
    editingScopeLabel,
  }
}
