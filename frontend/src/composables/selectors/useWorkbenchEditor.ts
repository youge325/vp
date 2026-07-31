// 视图选择器 — Workbench 编辑器双轨视图(激活素材 vs 默认预设)。
// 保持原 useEditor 的语义,但把它放进 selectors/ 命名空间。
//
// VP Workbench 有两套配置存储:
//   1. **工作台预设**(``presetStore.draftPreset``):用户当前编辑的通用
//      配置,自动持久化到本地。
//   2. **素材级配置**(``mediaItem.{decode,workflow,encode,output}Config``):
//      每个素材可以覆盖预设中的部分配置。
//
// 编辑路径(``patchDecode`` 等):
//   - 有激活素材 → 改 active + selected 的素材级配置
//   - 无激活素材 → 改预设草稿
//
// 读取路径(``editorConfig``):
//   - 有激活素材 → 返回素材级配置
//   - 无激活素材 → 返回预设草稿
//
// **不自动同步**:预设草稿变化时,**不会**自动套用到已选 items;素材级
// 配置变化时,**不会**反向写入预设。这是有意的:用户希望"调整预设不
// 影响已存在的素材"。
// 少数明确需要作为全局偏好保存的 workflow 字段,使用
// ``patchWorkflowAndPreset`` 显式双写当前可编辑素材和预设草稿。
//
import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { clonePresetData } from '@/services/preset/clone'
import { getEditingScopeLabel } from '@/services/format/labels'
import type { DecodeConfig, EncodeConfig, OutputConfig, WorkflowConfig } from '@/types/protocol'
import type { MediaItem } from '@/types/domain/media'

type ItemConfigPartial = {
  decodeConfig?: DecodeConfig
  encodeConfig?: EncodeConfig
  workflowConfig?: WorkflowConfig
  outputConfig?: OutputConfig
}

type EditableConfig = DecodeConfig | EncodeConfig | WorkflowConfig | OutputConfig

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

  function makePatcher<TConfig extends EditableConfig>(
    getItemConfig: (item: MediaItem) => TConfig,
    buildPartial: (config: TConfig) => ItemConfigPartial,
    patchPreset: (mutator: (c: TConfig) => void) => void,
    syncPreset = false,
  ): (mutator: (c: TConfig) => void) => void {
    return (mutator) => {
      if (activeItem.value) {
        const targetIds = mediaStore.getEditableTargetIds()
        for (const item of mediaStore.mediaItems) {
          if (!targetIds.has(item.id)) {
            continue
          }
          const next = clonePresetData(getItemConfig(item))
          mutator(next)
          mediaStore.replaceItemConfig(item.id, buildPartial(next))
        }
      }
      if (!activeItem.value || syncPreset) {
        patchPreset(mutator)
      }
    }
  }

  const patchDecode = makePatcher(
    (item) => item.decodeConfig,
    (next) => ({ decodeConfig: next }),
    presetStore.patchDecode,
  )

  const patchEncode = makePatcher(
    (item) => item.encodeConfig,
    (next) => ({ encodeConfig: next }),
    presetStore.patchEncode,
  )

  const patchWorkflow = makePatcher(
    (item) => item.workflowConfig,
    (next) => ({ workflowConfig: next }),
    presetStore.patchWorkflow,
  )

  const patchWorkflowAndPreset = makePatcher(
    (item) => item.workflowConfig,
    (next) => ({ workflowConfig: next }),
    presetStore.patchWorkflow,
    true,
  )

  const patchOutput = makePatcher(
    (item) => item.outputConfig,
    (next) => ({ outputConfig: next }),
    presetStore.patchOutput,
  )

  return {
    activeItem,
    isPresetMode,
    editorConfig,
    editorVideoCodec,
    patchDecode,
    patchEncode,
    patchWorkflow,
    patchWorkflowAndPreset,
    patchOutput,
  }
}

export function useEditingScope() {
  const mediaStore = useMediaStore()
  const targetLabel = computed(() =>
    getEditingScopeLabel(
      !mediaStore.activeItem,
      mediaStore.getEditableTargetIds().size || 1,
    ),
  )

  return { targetLabel }
}
