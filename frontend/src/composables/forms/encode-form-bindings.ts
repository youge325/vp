import { computed, type ComputedRef } from 'vue'

import { createCapabilityOptionBindings } from '@/composables/forms/capability-option-bindings'
import { createEncodeOutputSetters } from '@/composables/forms/encode-output-setters'
import { createEncodeProfileBindings } from '@/composables/forms/encode-profile-bindings'
import { createEncodeRateControlBindings } from '@/composables/forms/encode-rate-control-bindings'
import { CONTAINER_SELECT_OPTIONS } from '@/services/preset/io-options'
import { toNumberValue } from '@/services/preset/options'
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
  const outputSetters = createEncodeOutputSetters({ patchEncode, patchOutput })
  const segmentFramesValue = computed(() =>
    toNumberValue(editorConfig.value.outputConfig.segmentFrames),
  )
  const options = createCapabilityOptionBindings({
    getConfig: () => editorConfig.value.encodeConfig,
    patchConfig: patchEncode,
  })

  return {
    ...profile,
    ...rateControl,
    ...outputSetters,
    containerOptions: CONTAINER_SELECT_OPTIONS,
    segmentFramesValue,
    setEncodeOption: options.setOption,
    getEncodeOption: options.getOption,
    coerceOptionValue: options.coerceOptionValue,
  }
}
