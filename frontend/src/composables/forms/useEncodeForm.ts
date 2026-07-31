// 视图 form-binding — 编码模块。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { createCapabilityOptionBindings } from '@/composables/forms/capability-option-bindings'
import { createEncodeOutputSetters } from '@/composables/forms/encode-output-setters'
import { createEncodeProfileBindings } from '@/composables/forms/encode-profile-bindings'
import { createEncodeRateControlBindings } from '@/composables/forms/encode-rate-control-bindings'
import { CONTAINER_SELECT_OPTIONS } from '@/services/preset/io-options'
import { toNumberValue } from '@/services/preset/options'

export function useEncodeForm() {
  const envStore = useEnvStore()
  const { editorConfig, patchEncode, patchOutput } = useWorkbenchEditor()
  const profile = createEncodeProfileBindings({
    checkResult: computed(() => envStore.env.checkResult),
    editorConfig,
    patchEncode,
  })
  const rateControl = createEncodeRateControlBindings({
    currentEncoderProfile: profile.currentEncoderProfile,
    editorConfig,
    patchEncode,
  })
  const outputSetters = createEncodeOutputSetters({ patchEncode, patchOutput })
  const segmentFramesValue = computed(() =>
    toNumberValue(editorConfig.value.outputConfig.segmentFrames),
  )
  const options = createCapabilityOptionBindings({
    getConfig: () => editorConfig.value.encodeConfig,
    patchConfig: patchEncode,
  })

  return {
    encoderProfileOptions: profile.encoderProfileOptions,
    encoderOptions: profile.encoderOptions,
    setEncodeProfile: profile.setEncodeProfile,
    ...rateControl,
    ...outputSetters,
    containerOptions: CONTAINER_SELECT_OPTIONS,
    segmentFramesValue,
    setEncodeOption: options.setOption,
    getEncodeOption: options.getOption,
  }
}
