// 视图 form-binding — 增强模块(补帧 / 超分 / 动漫优化)。
// 这里只保留 store/env/editor 入口;字段绑定与返回对象组装下沉到
// ``createEnhanceFormBindings``。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { createEnhanceFormBindings } from '@/composables/forms/enhance-form-bindings'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'

export function useEnhanceForm() {
  const envStore = useEnvStore()
  const { activeItem, editorConfig, patchWorkflowAndPreset } = useWorkbenchEditor()

  const workflow = computed(() => editorConfig.value.workflowConfig)
  const checkResult = computed(() => envStore.env.checkResult)
  const activeVideoDimensions = computed(() => {
    const info = activeItem.value?.info
    if (!info) return null
    return { width: info.width, height: info.height }
  })

  return createEnhanceFormBindings({
    workflow,
    checkResult,
    activeVideoDimensions,
    patchWorkflow: patchWorkflowAndPreset,
  })
}
