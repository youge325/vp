import type { ComputedRef } from 'vue'

import { createEncodeOutputSetters } from '@/composables/forms/encode-output-setters'
import { createEncodeOutputState } from '@/composables/forms/encode-output-state'
import type { EncodeConfig, OutputConfig, WorkbenchPreset } from '@/types/protocol'

export interface EncodeOutputBindingParams {
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'encodeConfig' | 'outputConfig'>>
  patchEncode: (mutator: (config: EncodeConfig) => void) => void
  patchOutput: (mutator: (config: OutputConfig) => void) => void
}

export function createEncodeOutputBindings({
  editorConfig,
  patchEncode,
  patchOutput,
}: EncodeOutputBindingParams) {
  const state = createEncodeOutputState({ editorConfig })
  const setters = createEncodeOutputSetters({ patchEncode, patchOutput })

  return {
    ...state,
    ...setters,
  }
}
