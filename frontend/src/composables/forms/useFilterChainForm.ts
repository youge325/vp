// 视图 form-binding — 滤镜链编辑(预处理 / 后处理)。
//
// TODO(round-3): mutator 总是写到 presetStore.draftPreset,但当 activeItem 存在时应分发到 mediaItem。
// 应在 useWorkbenchEditor 增加统一写入 API,form 改走它。

import { computed } from 'vue'
import { usePresetStore } from '@/stores/preset'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import type { FilterStep, WorkflowConfig } from '@/types/protocol'

export type FilterStage = 'preprocess' | 'postprocess'

export function useFilterChainForm(stage: FilterStage) {
  const presetStore = usePresetStore()
  const { editorConfig } = useWorkbenchEditor()

  const enabled = computed({
    get: () => editorConfig.value.workflowConfig[stage].enabled,
    set: (value: boolean) => {
      presetStore.patchWorkflow((c: WorkflowConfig) => {
        c[stage].enabled = value
      })
    },
  })

  const filters = computed({
    get: () => editorConfig.value.workflowConfig[stage].filters,
    set: (value: FilterStep[]) => {
      presetStore.patchWorkflow((c: WorkflowConfig) => {
        c[stage].filters = value
      })
    },
  })

  return { enabled, filters }
}
