// 视图 form-binding — 滤镜链编辑(预处理 / 后处理)。

import { computed } from 'vue'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import type { FilterStep, WorkflowConfig } from '@/types/protocol'

type FilterStage = 'preprocess' | 'postprocess'

export function useFilterChainForm(stage: FilterStage) {
  const { editorConfig, patchWorkflow } = useWorkbenchEditor()

  const enabled = computed({
    get: () => editorConfig.value.workflowConfig[stage].enabled,
    set: (value: boolean) => {
      patchWorkflow((c: WorkflowConfig) => {
        c[stage].enabled = value
      })
    },
  })

  const filters = computed({
    get: () => editorConfig.value.workflowConfig[stage].filters,
    set: (value: FilterStep[]) => {
      patchWorkflow((c: WorkflowConfig) => {
        c[stage].filters = value
      })
    },
  })

  return { enabled, filters }
}
