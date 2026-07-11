import { computed, reactive } from 'vue'
import { describe, expect, it } from 'vitest'

import { createDefaultEncodeConfig, createDefaultWorkbenchPreset } from '@/services/preset/defaults'
import { createEncodeOutputState } from '@/composables/forms/encode-output-state'
import type { WorkbenchPreset } from '@/types/protocol'

function makeEditorConfig() {
  return reactive({
    encodeConfig: createDefaultEncodeConfig(null),
    outputConfig: { ...createDefaultWorkbenchPreset(null).outputConfig, outputDir: 'D:/Output' },
  } as Pick<WorkbenchPreset, 'encodeConfig' | 'outputConfig'>)
}

describe('encode output state', () => {
  it('derives container options and numeric segment frame value', () => {
    const editorConfig = makeEditorConfig()
    const state = createEncodeOutputState({
      editorConfig: computed(() => editorConfig),
    })

    expect(state.containerOptions.value).toEqual([
      { value: 'mp4', label: 'MP4' },
      { value: 'mkv', label: 'MKV' },
      { value: 'mov', label: 'MOV' },
    ])
    expect(state.segmentFramesValue.value).toBe(1000)

    editorConfig.outputConfig.segmentFrames = 250.5

    expect(state.segmentFramesValue.value).toBe(250.5)
  })
})
