// 视图选择器 — Workbench 编辑器双轨视图(激活素材 vs 默认预设)。
// 保持原 useEditor 的语义,但把它放进 selectors/ 命名空间。

import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import {
  cloneDecodeConfig,
  cloneEncodeConfig,
  cloneOutputConfig,
  cloneWorkflowConfig,
} from '@/services/preset/clone'
import { getEditingScopeLabel, type WorkflowStage } from '@/services/format/labels'
import type { DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig } from '@/types/protocol'

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

  function patchDecode(mutator: (config: DecodeConfig) => void): void {
    if (activeItem.value) {
      const next = cloneDecodeConfig(activeItem.value.decodeConfig)
      mutator(next)
      mediaStore.replaceItemConfig(activeItem.value.id, { decodeConfig: next })
    } else {
      presetStore.patchDecode(mutator)
    }
  }

  function patchEncode(mutator: (config: EncodeConfig) => void): void {
    if (activeItem.value) {
      const next = cloneEncodeConfig(activeItem.value.encodeConfig)
      mutator(next)
      mediaStore.replaceItemConfig(activeItem.value.id, { encodeConfig: next })
    } else {
      presetStore.patchEncode(mutator)
    }
  }

  function patchWorkflow(mutator: (config: WorkflowConfig) => void): void {
    if (activeItem.value) {
      const next = cloneWorkflowConfig(activeItem.value.workflowConfig)
      mutator(next)
      mediaStore.replaceItemConfig(activeItem.value.id, { workflowConfig: next })
    } else {
      presetStore.patchWorkflow(mutator)
    }
  }

  function patchOutput(mutator: (config: OutputConfig) => void): void {
    if (activeItem.value) {
      const next = cloneOutputConfig(activeItem.value.outputConfig)
      mutator(next)
      mediaStore.replaceItemConfig(activeItem.value.id, { outputConfig: next })
    } else {
      presetStore.patchOutput(mutator)
    }
  }

  return {
    activeItem,
    isPresetMode,
    editorConfig,
    editorVideoCodec,
    patchDecode,
    patchEncode,
    patchWorkflow,
    patchOutput,
  }
}

export function useEditingScope(stage: WorkflowStage) {
  const mediaStore = useMediaStore()
  const isPresetMode = computed(() => !mediaStore.activeItem)

  const label = computed(() =>
    getEditingScopeLabel(isPresetMode.value, mediaStore.selectedIds.length || 1, stage),
  )

  return {
    isPresetMode,
    targetLabel: computed(() => label.value.targetLabel),
    caption: computed(() => label.value.caption),
  }
}
