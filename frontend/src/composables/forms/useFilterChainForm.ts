// 视图 form-binding — 滤镜链编辑(预处理 / 后处理)。

import { computed } from 'vue'
import { usePresetStore } from '@/stores/preset'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import type { FilterStep } from '@/types/protocol'

export type FilterStage = 'preprocess' | 'postprocess'

export function useFilterChainForm(stage: FilterStage) {
  const presetStore = usePresetStore()
  const { editorConfig } = useWorkbenchEditor()

  const enabled = computed({
    get: () => editorConfig.value.workflowConfig[stage].enabled,
    set: (value: boolean) => {
      presetStore.patchWorkflow((c) => {
        c[stage].enabled = value
      })
    },
  })

  const filters = computed({
    get: () => editorConfig.value.workflowConfig[stage].filters,
    set: (value: FilterStep[]) => {
      presetStore.patchWorkflow((c) => {
        c[stage].filters = value
      })
    },
  })

  return { enabled, filters }
}
