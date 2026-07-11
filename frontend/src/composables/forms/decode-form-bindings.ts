import type { ComputedRef } from 'vue'

import { createCapabilityOptionBindings } from '@/composables/forms/capability-option-bindings'
import { createDecodeHardwareBindings } from '@/composables/forms/decode-hardware-bindings'
import { createDecodeProfileBindings } from '@/composables/forms/decode-profile-bindings'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { DecodeConfig, WorkbenchPreset } from '@/types/protocol'

interface DecodeFormBindingParams {
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'decodeConfig'>>
  editorVideoCodec: ComputedRef<string>
  patchDecode: (mutator: (config: DecodeConfig) => void) => void
}

export function createDecodeFormBindings({
  checkResult,
  editorConfig,
  editorVideoCodec,
  patchDecode,
}: DecodeFormBindingParams) {
  const profile = createDecodeProfileBindings({
    checkResult,
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
    coerceOptionValue: options.coerceOptionValue,
  }
}
