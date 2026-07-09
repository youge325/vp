import { normalizeSegmentFrames } from '@/services/preset/io-form-rules'
import { normalizeOutputDir } from '@/services/preset/normalize'
import type { EncodeConfig, OutputConfig } from '@/types/protocol'

interface EncodeOutputSetterParams {
  patchEncode: (mutator: (config: EncodeConfig) => void) => void
  patchOutput: (mutator: (config: OutputConfig) => void) => void
}

export function createEncodeOutputSetters({
  patchEncode,
  patchOutput,
}: EncodeOutputSetterParams) {
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
    setContainer,
    setKeepAudio,
    setOutputDir,
    setOpenOnComplete,
    setSegmentFrames,
  }
}
