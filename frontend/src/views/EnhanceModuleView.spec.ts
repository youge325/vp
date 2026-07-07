import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import EnhanceModuleView from './EnhanceModuleView.vue'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function makeEnv(): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { available: true, devices: ['GPU'], adapters: [], cudaAvailable: true },
    tensorBackends: { pytorch: true, paddle: true, onnx: true },
    tensorEngines: { pytorch: ['cuda'], paddle: ['cuda'], onnx: ['cuda'] },
    onnxRuntime: { available: true, providers: ['CUDAExecutionProvider'] },
    rifeModel: { available: true, version: '4.25', path: 'models/rife.pkl' },
    interpolationAlgorithms: [
      {
        name: 'rife',
        tensorBackends: ['pytorch'],
        models: ['4.25'],
      },
    ],
    superResolutionAlgorithms: [
      {
        name: 'ppmsvsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
        sequenceMode: 'recurrent',
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
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 5,
        sequenceMode: 'window',
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
    animeProfiles: ['clean-lines'],
  }
}

describe('EnhanceModuleView super-resolution frame wording', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-07-07T00:00:00Z',
    )
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
})
