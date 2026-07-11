import { describe, expect, it } from 'vitest'

import { createDefaultEncodeConfig, createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import { createEncodeOutputSetters } from '@/composables/forms/encode-output-setters'
import type { EncodeConfig, OutputConfig } from '@/types/protocol'

describe('encode output setters', () => {
  it('patches encode and output fields with existing normalization rules', () => {
    const encodeConfig = createDefaultEncodeConfig(null)
    const outputConfig = createDefaultWorkbenchPreset(null).outputConfig
    const setters = createEncodeOutputSetters({
      patchEncode: (mutator: (config: EncodeConfig) => void) => { mutator(encodeConfig) },
      patchOutput: (mutator: (config: OutputConfig) => void) => { mutator(outputConfig) },
    })

    setters.setContainer('mkv')
    setters.setKeepAudio(false)
    setters.setOutputDir('  D:/Video Output  ')
    setters.setOpenOnComplete(false)
    setters.setSegmentFrames(Number.NaN)

    expect(encodeConfig).toMatchObject({
      container: 'mkv',
      keepAudio: false,
    })
    expect(outputConfig).toEqual({
      outputDir: 'D:/Video Output',
      openOnComplete: false,
      segmentFrames: 1000,
    })
  })

  it('normalizes blank output directories to null and rounds positive segment frames', () => {
    const encodeConfig = createDefaultEncodeConfig(null)
    const outputConfig = { ...createDefaultWorkbenchPreset(null).outputConfig, outputDir: 'D:/Output' }
    const setters = createEncodeOutputSetters({
      patchEncode: (mutator: (config: EncodeConfig) => void) => { mutator(encodeConfig) },
      patchOutput: (mutator: (config: OutputConfig) => void) => { mutator(outputConfig) },
    })

    setters.setOutputDir('   ')
    setters.setSegmentFrames(24.6)

    expect(outputConfig.outputDir).toBeNull()
    expect(outputConfig.segmentFrames).toBe(25)
  })
})
