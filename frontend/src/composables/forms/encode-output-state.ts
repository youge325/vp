import { computed, type ComputedRef } from 'vue'

import { CONTAINER_SELECT_OPTIONS, toNumberValue } from '@/services/preset/io-options'
import type { WorkbenchPreset } from '@/types/protocol'

export interface EncodeOutputStateParams {
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'outputConfig'>>
}

export function createEncodeOutputState({ editorConfig }: EncodeOutputStateParams) {
  const containerOptions = computed(() => CONTAINER_SELECT_OPTIONS)
  const segmentFramesValue = computed(() =>
    toNumberValue(editorConfig.value.outputConfig.segmentFrames),
  )

  return {
    containerOptions,
    segmentFramesValue,
  }
}
