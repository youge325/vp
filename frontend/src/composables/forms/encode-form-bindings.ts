import type { ComputedRef } from 'vue'

import { createCapabilityOptionBindings } from '@/composables/forms/capability-option-bindings'
import { createEncodeOutputSetters } from '@/composables/forms/encode-output-setters'
import { createEncodeOutputState } from '@/composables/forms/encode-output-state'
import { createEncodeProfileBindings } from '@/composables/forms/encode-profile-bindings'
import { createEncodeRateControlBindings } from '@/composables/forms/encode-rate-control-bindings'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { EncodeConfig, OutputConfig, WorkbenchPreset } from '@/types/protocol'

interface EncodeFormBindingParams {
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'encodeConfig' | 'outputConfig'>>
  patchEncode: (mutator: (config: EncodeConfig) => void) => void
  patchOutput: (mutator: (config: OutputConfig) => void) => void
}

export function createEncodeFormBindings({
  checkResult,
  editorConfig,
  patchEncode,
  patchOutput,
}: EncodeFormBindingParams) {
  const profile = createEncodeProfileBindings({
    checkResult,
    editorConfig,
    patchEncode,
  })
  const rateControl = createEncodeRateControlBindings({
    currentEncoderProfile: profile.currentEncoderProfile,
    editorConfig,
    patchEncode,
  })
  const outputState = createEncodeOutputState({ editorConfig })
  const outputSetters = createEncodeOutputSetters({ patchEncode, patchOutput })
  const options = createCapabilityOptionBindings({
    getConfig: () => editorConfig.value.encodeConfig,
    patchConfig: patchEncode,
  })

  return {
    ...profile,
    ...rateControl,
    ...outputState,
    ...outputSetters,
    setEncodeOption: options.setOption,
    getEncodeOption: options.getOption,
    coerceOptionValue: options.coerceOptionValue,
  }
}
