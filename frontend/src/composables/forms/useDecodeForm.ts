// 视图 form-binding — 解码模块。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { createCapabilityOptionBindings } from '@/composables/forms/capability-option-bindings'
import { createDecodeHardwareBindings } from '@/composables/forms/decode-hardware-bindings'
import { createDecodeProfileBindings } from '@/composables/forms/decode-profile-bindings'

export function useDecodeForm() {
  const envStore = useEnvStore()
  const { editorConfig, editorVideoCodec, patchDecode } = useWorkbenchEditor()
  const profile = createDecodeProfileBindings({
    checkResult: computed(() => envStore.env.checkResult),
    editorConfig,
    editorVideoCodec,
    patchDecode,
  })
  const hardware = createDecodeHardwareBindings({
    currentDecoderProfile: profile.currentDecoderProfile,
    editorConfig,
    patchDecode,
  })
  const options = createCapabilityOptionBindings({
    getConfig: () => editorConfig.value.decodeConfig,
    patchConfig: patchDecode,
  })

  return {
    ...profile,
    ...hardware,
    setDecodeOption: options.setOption,
    getDecodeOption: options.getOption,
  }
}
