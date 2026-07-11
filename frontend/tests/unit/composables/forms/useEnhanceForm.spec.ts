import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useEnhanceForm } from '@/composables/forms/useEnhanceForm'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { createMediaItem } from '@/services/media/factory'
import { buildTaskRequest } from '@/services/task/request-builder'
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
    tensorEngines: { pytorch: ['cuda', 'tensorrt'], paddle: ['cuda', 'tensorrt'], onnx: ['cuda', 'tensorrt'] },
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
              parameterCount: 5670892,
              parameterBytes: 22683568,
              gflopsPerMegapixel: 18.5,
              activationBytesPerMegapixel: 694800000,
              runtimeOverheadBytes: 38000000,
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
              parameterCount: 5670892,
              parameterBytes: 22683568,
              gflopsPerMegapixel: 18.5,
              activationBytesPerMegapixel: 694800000,
              runtimeOverheadBytes: 38000000,
              inputModulo: 64,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
      },
      {
        name: 'rife-lite',
        tensorBackends: ['pytorch'],
        models: ['lite'],
        onnxModels: [],
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
        sequenceMode: 'recurrent',
        modelDetails: [
          {
            name: 'x4',
            label: 'PP-MSVSR',
            metrics: {
              parameterCount: 1453607,
              parameterBytes: 5814428,
              gflopsPerMegapixel: 120,
              activationBytesPerMegapixel: 1981031424,
              runtimeOverheadBytes: 2391117604,
              runtimeFrameCount: null,
              inputModulo: 4,
              analysisStatus: 'ok',
              analysisNotes: [],
              engineMetrics: {
                tensorrt: {
                  gflopsPerMegapixel: 120,
                  activationBytesPerMegapixel: 3688504346,
                  runtimeOverheadBytes: 0,
                  runtimeFrameCount: null,
                  analysisStatus: 'ok',
                  analysisNotes: ['TensorRT calibrated'],
                },
              },
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
        sequenceMode: 'window',
        modelDetails: [
          {
            name: 'x4',
            label: 'EDVR',
            metrics: {
              parameterCount: 20633827,
              parameterBytes: 82535308,
              gflopsPerMegapixel: 240,
              activationBytesPerMegapixel: 1000,
              runtimeOverheadBytes: 100,
              runtimeFrameCount: 5,
              inputModulo: 4,
              analysisStatus: 'ok',
              analysisNotes: [],
            },
          },
        ],
        weightPath: 'backend/models/super_resolution/paddlegan/edvr/EDVR_L_w_tsa_SRx4.pdparams',
        weightAvailable: true,
      },
      {
        name: 'custom-vsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        fixedScaleFactor: 4,
        inputFrameMode: 'editable_chunk',
        defaultNumFrames: 8,
        sequenceMode: 'recurrent',
      },
      {
        name: 'ppmsvsr-large',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
        sequenceMode: 'recurrent',
      },
      {
        name: 'basicvsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
        sequenceMode: 'recurrent',
      },
      {
        name: 'iconvsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
        sequenceMode: 'recurrent',
      },
      {
        name: 'basicvsr-plus-plus',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        defaultNumFrames: 10,
        sequenceMode: 'recurrent',
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
      'custom-vsr',
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

  it('uses PaddleGAN capability metadata for algorithms outside the old hard-coded name list', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.scaleFactor = 2
      workflow.superResolution.numFrames = 3
    })

    const form = useEnhanceForm()
    form.superResolutionAlgorithm = 'custom-vsr'

    expect(form.isPaddleGanSuperResolution).toBe(true)
    expect(form.superResolutionScale).toBe(4)
    expect(form.superResolutionNumFrames).toBe(8)
  })

  it('labels recurrent input frame chunks and exposes EDVR fixed neighbor window', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
      workflow.superResolution.numFrames = 10
    })

    const form = useEnhanceForm()

    expect(form.isSuperResolutionInputFramesEditable).toBe(true)
    expect(form.superResolutionInputFramesLabel).toBe('每块输入帧数')
    expect(form.superResolutionInputFramesHint).toContain('连续输入帧数')
    expect(form.superResolutionInputFramesHint).toContain('不是邻帧窗口')
    expect(form.superResolutionFixedWindowRows).toEqual([])

    form.superResolutionAlgorithm = 'edvr'
    form.superResolutionNumFrames = 10

    expect(form.isSuperResolutionInputFramesEditable).toBe(false)
    expect(form.superResolutionNumFrames).toBe(5)
    expect(form.superResolutionFixedWindowRows).toEqual([
      { label: '邻帧窗口', value: '5 帧（固定）' },
    ])
  })

  it('uses EDVR fixed neighbor window for memory estimates regardless of stale numFrames', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'edvr'
      workflow.superResolution.scaleFactor = 4
      workflow.superResolution.numFrames = 10
    })
    const item = createMediaItem('/video/tai-chi.mp4', presetStore.draftPreset)
    mediaStore.appendItems([item])
    mediaStore.setItemInfo(item.id, {
      type: 'info',
      fps: 27,
      frames: 120,
      duration: 4.4,
      width: 640,
      height: 288,
      hasAudio: true,
      videoCodec: 'h264',
    })

    const form = useEnhanceForm()
    const before = form.superResolutionRuntimeEstimate?.vramBytes

    form.superResolutionNumFrames = 2

    expect(form.superResolutionRuntimeEstimate?.vramBytes).toBe(before)
  })

  it('applies recurrent input frame edits to every selected media item before task start', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
      workflow.superResolution.scaleFactor = 4
      workflow.superResolution.numFrames = 10
    })
    const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
    const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
    mediaStore.appendItems([first, second])

    const form = useEnhanceForm()
    form.superResolutionNumFrames = 5

    expect(first.workflowConfig.superResolution.numFrames).toBe(5)
    expect(second.workflowConfig.superResolution.numFrames).toBe(5)
    expect(buildTaskRequest(second).workflowConfig.superResolution.numFrames).toBe(5)
  })

  it('persists all enhance page edits while applying them to every selected media item', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.interpolation.enabled = false
      workflow.interpolation.tensorBackend = 'pytorch'
      workflow.interpolation.engine = 'cuda'
      workflow.interpolation.algorithm = 'rife'
      workflow.interpolation.model = '4.25'
      workflow.interpolation.onnxModel = ''
      workflow.fpsMode = 'target'
      workflow.interpolation.targetFps = 60
      workflow.interpolation.multi = 2
      workflow.interpolation.scale = 1
      workflow.interpolation.fp16 = false
      workflow.superResolution.enabled = false
      workflow.superResolution.tensorBackend = 'onnx'
      workflow.superResolution.engine = 'cuda'
      workflow.superResolution.algorithm = 'placeholder'
      workflow.superResolution.scaleFactor = 2
      workflow.superResolution.onnxModel = ''
      workflow.superResolution.numFrames = 10
      workflow.processOrder = 'super_resolution_then_interpolation'
      workflow.anime.enabled = false
      workflow.anime.profile = 'clean-lines'
      workflow.anime.denoise = 10
      workflow.anime.edgeBoost = 15
    })
    const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
    const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
    mediaStore.appendItems([first, second])

    const form = useEnhanceForm()
    form.interpolationEnabled = true
    form.interpolationAlgorithm = 'rife-lite'
    form.interpolationModel = 'lite'
    form.interpolationEngine = 'tensorrt'
    form.targetFps = 72
    form.fpsMode = 'multi'
    form.interpolationMulti = 4
    form.interpolationScale = 0.5
    form.interpolationFp16 = true

    expect(first.workflowConfig.interpolation.algorithm).toBe('rife-lite')
    expect(second.workflowConfig.interpolation.algorithm).toBe('rife-lite')
    expect(presetStore.draftPreset.workflowConfig.interpolation.algorithm).toBe('rife-lite')
    expect(first.workflowConfig.interpolation.model).toBe('lite')
    expect(second.workflowConfig.interpolation.model).toBe('lite')
    expect(presetStore.draftPreset.workflowConfig.interpolation.model).toBe('lite')

    form.interpolationBackend = 'onnx'
    form.interpolationEngine = 'tensorrt'
    form.interpolationOnnxModel = 'rife_v4.25.onnx'

    expect(first.workflowConfig.interpolation.onnxModel).toBe('rife_v4.25.onnx')
    expect(second.workflowConfig.interpolation.onnxModel).toBe('rife_v4.25.onnx')
    expect(presetStore.draftPreset.workflowConfig.interpolation.onnxModel).toBe('rife_v4.25.onnx')

    form.superResolutionEnabled = true
    form.superResolutionScale = 4
    form.superResolutionOnnxModel = 'sr_x2.onnx'

    expect(first.workflowConfig.superResolution.onnxModel).toBe('sr_x2.onnx')
    expect(second.workflowConfig.superResolution.onnxModel).toBe('sr_x2.onnx')
    expect(presetStore.draftPreset.workflowConfig.superResolution.onnxModel).toBe('sr_x2.onnx')

    form.superResolutionBackend = 'paddle'
    form.superResolutionAlgorithm = 'ppmsvsr'
    form.superResolutionEngine = 'tensorrt'
    form.superResolutionNumFrames = 5
    form.processOrder = 'frame_interpolation_then_super_resolution'
    form.animeEnabled = true
    form.animeProfile = 'clean-lines'
    form.animeDenoise = 24
    form.animeEdgeBoost = 36

    for (const workflow of [
      first.workflowConfig,
      second.workflowConfig,
      presetStore.draftPreset.workflowConfig,
      buildTaskRequest(second).workflowConfig,
    ]) {
      expect(workflow.interpolation.enabled).toBe(true)
      expect(workflow.interpolation.tensorBackend).toBe('onnx')
      expect(workflow.interpolation.engine).toBe('tensorrt')
      expect(workflow.interpolation.algorithm).toBe('rife')
      expect(workflow.interpolation.model).toBe('4.25')
      expect(workflow.interpolation.onnxModel).toBe('rife_v4.25.onnx')
      expect(workflow.fpsMode).toBe('multi')
      expect(workflow.interpolation.targetFps).toBe(72)
      expect(workflow.interpolation.multi).toBe(4)
      expect(workflow.interpolation.scale).toBe(0.5)
      expect(workflow.interpolation.fp16).toBe(true)
      expect(workflow.superResolution.enabled).toBe(true)
      expect(workflow.superResolution.tensorBackend).toBe('paddle')
      expect(workflow.superResolution.engine).toBe('tensorrt')
      expect(workflow.superResolution.algorithm).toBe('ppmsvsr')
      expect(workflow.superResolution.scaleFactor).toBe(4)
      expect(workflow.superResolution.onnxModel).toBe('')
      expect(workflow.superResolution.numFrames).toBe(5)
      expect(workflow.processOrder).toBe('frame_interpolation_then_super_resolution')
      expect(workflow.anime.enabled).toBe(true)
      expect(workflow.anime.profile).toBe('clean-lines')
      expect(workflow.anime.denoise).toBe(24)
      expect(workflow.anime.edgeBoost).toBe(36)
    }
  })

  it('persists process order while applying it to every selected media item', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.processOrder = 'super_resolution_then_interpolation'
    })
    const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
    const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
    mediaStore.appendItems([first, second])

    const form = useEnhanceForm()
    form.processOrder = 'frame_interpolation_then_super_resolution'

    expect(first.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(second.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(presetStore.draftPreset.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
  })

  it('persists anime enabled while applying it to every selected media item', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.anime.enabled = false
    })
    const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
    const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
    mediaStore.appendItems([first, second])

    const form = useEnhanceForm()
    form.animeEnabled = true

    expect(first.workflowConfig.anime.enabled).toBe(true)
    expect(second.workflowConfig.anime.enabled).toBe(true)
    expect(presetStore.draftPreset.workflowConfig.anime.enabled).toBe(true)
  })

  it('persists anime detail edits while applying them to selected media items', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.anime.profile = 'clean-lines'
      workflow.anime.denoise = 10
    })
    const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
    const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
    mediaStore.appendItems([first, second])

    const form = useEnhanceForm()
    form.animeProfile = 'line-art'
    form.animeDenoise = 24

    expect(first.workflowConfig.anime.profile).toBe('line-art')
    expect(second.workflowConfig.anime.profile).toBe('line-art')
    expect(first.workflowConfig.anime.denoise).toBe(24)
    expect(second.workflowConfig.anime.denoise).toBe(24)
    expect(presetStore.draftPreset.workflowConfig.anime.profile).toBe('line-art')
    expect(presetStore.draftPreset.workflowConfig.anime.denoise).toBe(24)
  })

  it('applies EDVR fixed window defaults to every selected media item', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
      workflow.superResolution.scaleFactor = 4
      workflow.superResolution.numFrames = 10
    })
    const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
    const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
    mediaStore.appendItems([first, second])

    const form = useEnhanceForm()
    form.superResolutionAlgorithm = 'edvr'

    expect(first.workflowConfig.superResolution.algorithm).toBe('edvr')
    expect(first.workflowConfig.superResolution.numFrames).toBe(5)
    expect(second.workflowConfig.superResolution.algorithm).toBe('edvr')
    expect(second.workflowConfig.superResolution.numFrames).toBe(5)
    expect(buildTaskRequest(second).workflowConfig.superResolution.numFrames).toBe(5)
    expect(presetStore.draftPreset.workflowConfig.superResolution.algorithm).toBe('edvr')
    expect(presetStore.draftPreset.workflowConfig.superResolution.numFrames).toBe(5)
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
    expect(form.interpolationMetricRows[0].value).toBe('5.67M')
  })

  it('estimates default SR to interpolation order and exposes combined peak VRAM', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.processOrder = 'super_resolution_then_interpolation'
      workflow.interpolation.enabled = true
      workflow.interpolation.tensorBackend = 'pytorch'
      workflow.interpolation.model = '4.25'
      workflow.interpolation.fp16 = false
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
      workflow.superResolution.scaleFactor = 4
      workflow.superResolution.numFrames = 10
    })
    const item = createMediaItem('/video/tai-chi.mp4', presetStore.draftPreset)
    mediaStore.appendItems([item])
    mediaStore.setItemInfo(item.id, {
      type: 'info',
      fps: 27,
      frames: 120,
      duration: 4.4,
      width: 640,
      height: 288,
      hasAudio: true,
      videoCodec: 'h264',
    })

    const form = useEnhanceForm()

    expect(form.interpolationRuntimeEstimate?.effectiveWidth).toBe(2560)
    expect(form.interpolationRuntimeEstimate?.effectiveHeight).toBe(1152)
    expect(form.interpolationMetricRows[2].value).toBe('1.96 GiB')
    expect(form.superResolutionMetricRows[2].value).toBe('5.63 GiB')
    expect(form.combinedVramMetricRows[0].value).toBe('5.63 GiB')
  })

  it('uses selected TensorRT engine metrics for super-resolution memory estimates', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.engine = 'tensorrt'
      workflow.superResolution.algorithm = 'ppmsvsr'
      workflow.superResolution.scaleFactor = 4
      workflow.superResolution.numFrames = 5
    })
    const item = createMediaItem('/video/tai-chi.mp4', presetStore.draftPreset)
    mediaStore.appendItems([item])
    mediaStore.setItemInfo(item.id, {
      type: 'info',
      fps: 27,
      frames: 120,
      duration: 4.4,
      width: 640,
      height: 288,
      hasAudio: true,
      videoCodec: 'h264',
    })

    const form = useEnhanceForm()

    expect(form.superResolutionMetricRows[1].value).toBe('22.1 GFLOPs')
    expect(form.superResolutionMetricRows[2].value).toBe('3.17 GiB')
  })
})
