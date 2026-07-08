import { computed, type ComputedRef } from 'vue'

import { normalizeOutputDir } from '@/services/preset/normalize'
import { normalizeSegmentFrames } from '@/services/preset/io-form-rules'
import { CONTAINER_SELECT_OPTIONS, toNumberValue } from '@/services/preset/io-options'
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
  const containerOptions = computed(() => CONTAINER_SELECT_OPTIONS)
  const segmentFramesValue = computed(() =>
    toNumberValue(editorConfig.value.outputConfig.segmentFrames),
  )

  function setContainer(value: string): void {
    patchEncode((config: EncodeConfig) => {
      config.container = value
    })
  }

  function setKeepAudio(value: boolean): void {
    patchEncode((config: EncodeConfig) => {
      config.keepAudio = value
    })
  }

  function setOutputDir(value: string): void {
    patchOutput((config: OutputConfig) => {
      config.outputDir = normalizeOutputDir(value)
    })
  }

  function setOpenOnComplete(value: OutputConfig['openOnComplete']): void {
    patchOutput((config: OutputConfig) => {
      config.openOnComplete = value
    })
  }

  function setSegmentFrames(value: number): void {
    patchOutput((config: OutputConfig) => {
      config.segmentFrames = normalizeSegmentFrames(value)
    })
  }

  return {
    containerOptions,
    segmentFramesValue,
    setContainer,
    setKeepAudio,
    setOutputDir,
    setOpenOnComplete,
    setSegmentFrames,
  }
}
