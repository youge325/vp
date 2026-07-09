import { computed, type ComputedRef } from 'vue'

import { createCapabilityOptionBindings } from '@/composables/forms/capability-option-bindings'
import { createEncodeOutputBindings } from '@/composables/forms/encode-output-bindings'
import { createEncodeProfileBindings } from '@/composables/forms/encode-profile-bindings'
import { createEncodeRateControlBindings } from '@/composables/forms/encode-rate-control-bindings'
import type { CapabilityValue } from '@/types/domain/capability'
import type { EnvironmentCheckResult } from '@/types/domain/env'
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
  const output = createEncodeOutputBindings({
    editorConfig,
    patchEncode,
    patchOutput,
  })
  const options = createCapabilityOptionBindings({
    optionValues: computed(() => editorConfig.value.encodeConfig.options),
    patchOptions: (nextOptions: Record<string, CapabilityValue>) => {
      patchEncode((config: EncodeConfig) => {
        config.options = nextOptions
      })
    },
  })

  return {
    ...profile,
    ...rateControl,
    ...output,
    setEncodeOption: options.setOption,
    getEncodeOption: options.getOption,
    coerceOptionValue: options.coerceOptionValue,
  }
}
