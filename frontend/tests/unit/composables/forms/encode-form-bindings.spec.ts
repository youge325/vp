import { computed, reactive, ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultEncodeConfig, createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import { createEncodeFormBindings } from '@/composables/forms/encode-form-bindings'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { EncodeConfig, OutputConfig, WorkbenchPreset } from '@/types/protocol'
import { createEncodingEnvironment } from '../../fixtures/environment'

function makeBindings() {
  const checkResult = ref<EnvironmentCheckResult | null>(createEncodingEnvironment())
  const editorConfig = reactive({
    encodeConfig: createDefaultEncodeConfig(checkResult.value),
    outputConfig: createDefaultWorkbenchPreset(null).outputConfig,
  } as WorkbenchPreset)
  const bindings = createEncodeFormBindings({
    checkResult: computed(() => checkResult.value),
    editorConfig: computed(() => editorConfig),
    patchEncode: (mutator: (config: EncodeConfig) => void) => { mutator(editorConfig.encodeConfig) },
    patchOutput: (mutator: (config: OutputConfig) => void) => { mutator(editorConfig.outputConfig) },
  })
  return { bindings, editorConfig }
}

describe('encode form bindings', () => {
  it('derives encoder profiles, profile options, and rate-control view state', () => {
    const { bindings } = makeBindings()

    expect(bindings.encoderProfileOptions.value).toEqual([
      { value: 'libx265', label: 'x265' },
      { value: 'hevc_nvenc', label: 'NVENC H.265' },
    ])
    expect(bindings.encoderOptions.value.map((option) => option.name)).toEqual(['preset', 'tune'])
    expect(bindings.rateControlOptions.value).toEqual([{ value: 'cq', label: 'CQ' }])
    expect(bindings.rateControlDisabled.value).toBe(false)
    expect(bindings.rateControlModeHint.value).toBeUndefined()
    expect(bindings.rateControlValue.value).toBe(24)
    expect(bindings.containerOptions).toEqual([
      { value: 'mp4', label: 'MP4' },
      { value: 'mkv', label: 'MKV' },
      { value: 'mov', label: 'MOV' },
    ])
    expect(bindings.segmentFramesValue.value).toBe(1000)
  })

  it('applies encode profile, rate-control, option, and container setters through patch functions', () => {
    const { bindings, editorConfig } = makeBindings()

    bindings.setEncodeProfile('hevc_nvenc')
    bindings.setRateControlModeValue('cq')
    bindings.setRateControlValue(26)
    bindings.setEncodeOption('tune', 'uhq')
    bindings.setContainer('mkv')
    bindings.setKeepAudio(false)

    expect(editorConfig.encodeConfig).toMatchObject({
      codec: 'hevc_nvenc',
      family: 'nvidia',
      rateControl: { mode: 'cq', value: 26 },
      options: { preset: 'p5', tune: 'uhq' },
      container: 'mkv',
      keepAudio: false,
    })
    expect(bindings.getEncodeOption(bindings.encoderOptions.value[1])).toBe('uhq')
  })

  it('normalizes output directory, open-on-complete, and segment frames through output patching', () => {
    const { bindings, editorConfig } = makeBindings()

    bindings.setOutputDir('  D:/Video Output  ')
    bindings.setOpenOnComplete(false)
    bindings.setSegmentFrames(Number.NaN)

    expect(editorConfig.outputConfig).toEqual({
      outputDir: 'D:/Video Output',
      openOnComplete: false,
      segmentFrames: 1000,
    })
  })
})
