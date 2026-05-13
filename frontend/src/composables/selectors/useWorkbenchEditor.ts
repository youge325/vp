// 视图选择器 — Workbench 编辑器双轨视图(激活素材 vs 默认预设)。
// 保持原 useEditor 的语义,但把它放进 selectors/ 命名空间。
//
// Phase D.4.6 — 双轨同步语义文档化:
//
// VP Workbench 有两套配置存储:
//   1. **工作台预设**(``presetStore.draftPreset``):用户当前编辑的通用
//      配置,自动持久化到本地。
//   2. **素材级配置**(``mediaItem.{decode,workflow,encode,output}Config``):
//      每个素材可以覆盖预设中的部分配置。
//
// 编辑路径(``patchDecode`` 等):
//   - 有激活素材 → 改素材级配置
//   - 无激活素材 → 改预设草稿
//
// 读取路径(``editorConfig``):
//   - 有激活素材 → 返回素材级配置
//   - 无激活素材 → 返回预设草稿
//
// **不自动同步**:预设草稿变化时,**不会**自动套用到已选 items;素材级
// 配置变化时,**不会**反向写入预设。这是有意的:用户希望"调整预设不
// 影响已存在的素材"。
//
// 如果用户希望把预设草稿手动套用到当前选中的所有素材,使用
// ``useMediaImport.applyDraftToSelectedItems()``。Phase D 暂未在 UI 上
// 暴露按钮,作为后续 D.4.6 第二步(显式"应用到选中")的钩子保留。

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
