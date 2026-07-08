// 视图 form-binding — 解码模块。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { createDecodeFormBindings } from '@/composables/forms/decode-form-bindings'

export function useDecodeForm() {
  const envStore = useEnvStore()
  const { editorConfig, editorVideoCodec, patchDecode } = useWorkbenchEditor()

  return createDecodeFormBindings({
    checkResult: computed(() => envStore.env.checkResult),
    editorConfig,
    editorVideoCodec,
    patchDecode,
  })
}
