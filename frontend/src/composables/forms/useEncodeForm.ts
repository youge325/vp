// 视图 form-binding — 编码模块。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { createEncodeFormBindings } from '@/composables/forms/encode-form-bindings'

export function useEncodeForm() {
  const envStore = useEnvStore()
  const { editorConfig, patchEncode, patchOutput } = useWorkbenchEditor()

  return createEncodeFormBindings({
    checkResult: computed(() => envStore.env.checkResult),
    editorConfig,
    patchEncode,
    patchOutput,
  })
}
