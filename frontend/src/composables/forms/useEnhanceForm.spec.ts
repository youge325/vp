import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useEnhanceForm } from './useEnhanceForm'
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
    rifeModel: { available: true, version: '4.25', path: 'models/interpolation/rife/rife_v4.25.onnx' },
    interpolationAlgorithms: [
      {
        name: 'rife',
        tensorBackends: ['pytorch', 'onnx'],
        models: ['4.25'],
        onnxModels: ['rife_v4.25.onnx'],
      },
    ],
    superResolutionAlgorithms: [
      { name: 'placeholder', tensorBackends: ['onnx'], models: [], onnxModels: ['sr_x2.onnx'] },
      {
        name: 'ppmsvsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
        weightUrl: 'https://paddlegan.bj.bcebos.com/models/PP-MSVSR_reds_x4.pdparams',
        weightPath: 'backend/models/super_resolution/paddlegan/ppmsvsr/PP-MSVSR_reds_x4.pdparams',
        weightAvailable: false,
      },
    ],
    animeProfiles: ['clean-lines'],
  }
}

describe('useEnhanceForm PaddleGAN super-resolution', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(
      { result: makeEnv(), source: 'probe', checkedAt: null },
      '2026-06-21T00:00:00Z',
    )
  })

  it('keeps super-resolution backend independent and applies PaddleGAN defaults', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.interpolation.enabled = true
      workflow.interpolation.tensorBackend = 'pytorch'
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'onnx'
      workflow.superResolution.autoDownloadWeights = false
    })

    const form = useEnhanceForm()
    expect(form.superResolutionAlgorithms.map((algorithm) => algorithm.name)).toEqual(['placeholder'])

    form.superResolutionBackend = 'paddle'
    expect(form.superResolutionAlgorithms.map((algorithm) => algorithm.name)).toEqual(['ppmsvsr'])

    form.superResolutionAlgorithm = 'ppmsvsr'
    expect(form.superResolutionBackend).toBe('paddle')
    expect(form.superResolutionScale).toBe(4)
    expect(form.superResolutionNumFrames).toBe(10)
    expect(form.interpolationBackend).toBe('onnx')
    expect(form.interpolationOnnxModel).toBe('rife_v4.25.onnx')

    form.superResolutionScale = 2
    expect(form.superResolutionScale).toBe(4)

    form.superResolutionAutoDownloadWeights = true
    expect(presetStore.draftPreset.workflowConfig.superResolution.autoDownloadWeights).toBe(true)
  })
})
