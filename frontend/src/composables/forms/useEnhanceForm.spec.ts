import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useEnhanceForm } from './useEnhanceForm'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { createMediaItem } from '@/services/media/factory'
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
        modelDetails: [
          {
            name: '4.25',
            label: 'RIFE 4.25',
            metrics: {
              parameterCount: 5664776,
              parameterBytes: 22659104,
              gflopsPerMegapixel: 18.5,
              activationBytesPerMegapixel: 220000000,
              inputModulo: 64,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
        onnxModelDetails: [
          {
            name: 'rife_v4.25.onnx',
            label: 'rife_v4.25.onnx',
            metrics: {
              parameterCount: 5664776,
              parameterBytes: 22659104,
              gflopsPerMegapixel: 18.5,
              activationBytesPerMegapixel: 220000000,
              inputModulo: 64,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
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
        modelDetails: [
          {
            name: 'x4',
            label: 'PP-MSVSR',
            metrics: {
              parameterCount: 15200000,
              parameterBytes: 60800000,
              gflopsPerMegapixel: 120,
              activationBytesPerMegapixel: 360000000,
              inputModulo: 4,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
        weightPath: 'backend/models/super_resolution/paddlegan/ppmsvsr/PP-MSVSR_reds_x4.pdparams',
        weightAvailable: false,
      },
      {
        name: 'edvr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 5,
        weightPath: 'backend/models/super_resolution/paddlegan/edvr/EDVR_L_w_tsa_SRx4.pdparams',
        weightAvailable: true,
      },
      {
        name: 'ppmsvsr-large',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
      },
      {
        name: 'basicvsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
      },
      {
        name: 'iconvsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
      },
      {
        name: 'basicvsr-plus-plus',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
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
    })

    const form = useEnhanceForm()
    expect(form.superResolutionAlgorithms.map((algorithm) => algorithm.name)).toEqual(['placeholder'])

    form.superResolutionBackend = 'paddle'
    expect(form.superResolutionAlgorithms.map((algorithm) => algorithm.name)).toEqual([
      'ppmsvsr',
      'edvr',
      'ppmsvsr-large',
      'basicvsr',
      'iconvsr',
      'basicvsr-plus-plus',
    ])

    form.superResolutionAlgorithm = 'ppmsvsr'
    expect(form.superResolutionBackend).toBe('paddle')
    expect(form.superResolutionScale).toBe(4)
    expect(form.superResolutionNumFrames).toBe(10)
    expect(form.interpolationBackend).toBe('onnx')
    expect(form.interpolationOnnxModel).toBe('rife_v4.25.onnx')

    form.superResolutionScale = 2
    expect(form.superResolutionScale).toBe(4)
    expect('superResolutionAutoDownloadWeights' in form).toBe(false)
  })

  it('applies PaddleGAN defaults to every supported PaddleGAN VSR algorithm', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.scaleFactor = 2
      workflow.superResolution.numFrames = 3
    })

    const form = useEnhanceForm()

    form.superResolutionAlgorithm = 'edvr'
    expect(form.superResolutionScale).toBe(4)
    expect(form.superResolutionNumFrames).toBe(5)

    form.superResolutionScale = 2
    form.superResolutionNumFrames = 3
    form.superResolutionAlgorithm = 'basicvsr'
    expect(form.superResolutionScale).toBe(4)
    expect(form.superResolutionNumFrames).toBe(10)
  })

  it('exposes selected model details and current-video runtime estimates', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    const item = createMediaItem('/video/clip.mp4', presetStore.draftPreset)
    mediaStore.appendItems([item])
    mediaStore.setItemInfo(item.id, {
      type: 'info',
      fps: 30,
      frames: 120,
      duration: 4,
      width: 1920,
      height: 1080,
      hasAudio: true,
      videoCodec: 'h264',
    })

    const form = useEnhanceForm()

    expect(form.currentInterpolationModelDetail?.name).toBe('4.25')
    expect(form.interpolationRuntimeEstimate?.effectiveHeight).toBe(1088)
    expect(form.interpolationMetricRows[0].value).toBe('5.66M')
  })
})
