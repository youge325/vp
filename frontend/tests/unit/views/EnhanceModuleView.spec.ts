import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import EnhanceModuleView from '@/views/EnhanceModuleView.vue'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createEnvironmentPayload, createEnvironmentResult } from '../fixtures/environment'

function makeEnv(): EnvironmentCheckResult {
  return createEnvironmentResult({
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: ['cuda'], paddle: ['cuda'], onnx: ['cuda'] },
    interpolationAlgorithms: [
      {
        name: 'rife',
        family: 'rife',
        tensorBackends: ['pytorch'],
        models: ['4.25'],
        inputFrameMode: 'none',
      },
    ],
    superResolutionAlgorithms: [
      {
        name: 'ppmsvsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        fixedScaleFactor: 4,
        defaultNumFrames: 10,
        inputFrameMode: 'editable_chunk',
        modelDetails: [
          {
            name: 'x4',
            label: 'PP-MSVSR',
            metrics: {
              parameterCount: 1,
              parameterBytes: 4,
              gflopsPerMegapixel: 1,
              activationBytesPerMegapixel: 1,
              inputModulo: 4,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
      },
      {
        name: 'edvr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        fixedScaleFactor: 4,
        defaultNumFrames: 5,
        inputFrameMode: 'fixed_window',
        modelDetails: [
          {
            name: 'x4',
            label: 'EDVR',
            metrics: {
              parameterCount: 1,
              parameterBytes: 4,
              gflopsPerMegapixel: 1,
              activationBytesPerMegapixel: 1,
              runtimeFrameCount: 5,
              inputModulo: 4,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
      },
    ],
    runtimeMode: 'bundled',
  })
}

describe('EnhanceModuleView super-resolution frame wording', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(createEnvironmentPayload(makeEnv()))
  })

  it('explains recurrent input frame chunks as distinct from neighbor windows', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
    })

    const wrapper = mount(EnhanceModuleView)

    expect(wrapper.text()).toContain('每块输入帧数')
    expect(wrapper.text()).toContain('每次送入超分模型的连续输入帧数')
    expect(wrapper.text()).toContain('不是邻帧窗口')
  })

  it('shows EDVR fixed neighbor window instead of editable input frame chunks', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'edvr'
    })

    const wrapper = mount(EnhanceModuleView)

    expect(wrapper.text()).not.toContain('每块输入帧数')
    expect(wrapper.text()).toContain('邻帧窗口')
    expect(wrapper.text()).toContain('5 帧（固定）')
  })

  it('does not render the removed standalone Anime optimization section', () => {
    const wrapper = mount(EnhanceModuleView)

    expect(wrapper.text()).not.toContain('动漫优化')
  })
})
