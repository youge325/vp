import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { getEditingScopeLabel } from '@/services/format'

/**
 * 组合编辑器相关状态。
 *
 * 将原本分散在 media.ts / preset.ts 中的 editor 逻辑集中管理，
 * 视图组件通过此 composable 获取统一的编辑配置，无需同时引用多个 store。
 */
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
    presetStore,
    mediaStore,
  }
}
