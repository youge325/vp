import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useEnhanceForm } from '@/composables/forms/useEnhanceForm'
import { useEnvStore } from '@/stores/env'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { createMediaItem } from '@/services/media/factory'
import type { WorkflowConfig } from '@/types/protocol'
import {
  createEnhanceEnvironment,
  createEnvironmentPayload,
} from '../../fixtures/environment'

function seedSelectedPair(configure: (workflow: WorkflowConfig) => void) {
  const mediaStore = useMediaStore()
  const presetStore = usePresetStore()
  presetStore.patchWorkflow(configure)
  const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
  const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
  mediaStore.appendItems([first, second])
  return { first, second, presetStore }
}

describe('useEnhanceForm PaddleGAN super-resolution', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(createEnvironmentPayload(createEnhanceEnvironment()))
  })

  it('keeps super-resolution backend independent and applies PaddleGAN defaults', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.interpolation.enabled = true
      workflow.interpolation.tensorBackend = 'pytorch'
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'onnx'
    })

    const model = useEnhanceForm()
    const form = model.fields
    expect(model.options.value.superResolutionAlgorithmOptions.map(({ value }) => value)).toEqual([
      'placeholder',
    ])

    form.superResolutionBackend = 'paddle'
    expect(model.options.value.superResolutionAlgorithmOptions.map(({ value }) => value)).toEqual([
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

  it('converts the two numeric select values at the composition boundary', () => {
    const { fields, actions } = useEnhanceForm()

    actions.setInterpolationMulti('4')
    actions.setSuperResolutionScale('4')

    expect(fields.interpolationMulti).toBe(4)
    expect(fields.superResolutionScale).toBe(4)
  })

  it('applies PaddleGAN defaults to every supported PaddleGAN VSR algorithm', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.scaleFactor = 2
      workflow.superResolution.numFrames = 3
    })

    const { fields: form } = useEnhanceForm()

    form.superResolutionAlgorithm = 'edvr'
    expect(form.superResolutionScale).toBe(4)
    expect(form.superResolutionNumFrames).toBe(5)

    form.superResolutionScale = 2
    form.superResolutionNumFrames = 3
    form.superResolutionAlgorithm = 'basicvsr'
    expect(form.superResolutionScale).toBe(4)
    expect(form.superResolutionNumFrames).toBe(10)
  })

  it('uses PaddleGAN capability metadata for every advertised algorithm', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.scaleFactor = 2
      workflow.superResolution.numFrames = 3
    })

    const { fields: form } = useEnhanceForm()
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

    const model = useEnhanceForm()
    const form = model.fields

    expect(form.isSuperResolutionInputFramesEditable).toBe(true)
    expect(form.superResolutionInputFramesLabel).toBe('每块输入帧数')
    expect(form.superResolutionInputFramesHint).toContain('连续输入帧数')
    expect(form.superResolutionInputFramesHint).toContain('不是邻帧窗口')
    expect(model.metrics.value.superResolutionFixedWindowRows).toEqual([])

    form.superResolutionAlgorithm = 'edvr'
    form.superResolutionNumFrames = 10

    expect(form.isSuperResolutionInputFramesEditable).toBe(false)
    expect(form.superResolutionNumFrames).toBe(5)
    expect(model.metrics.value.superResolutionFixedWindowRows).toEqual([
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
      fps: 27,
      width: 640,
      height: 288,
      videoCodec: 'h264',
    })

    const model = useEnhanceForm()
    const form = model.fields
    const before = model.metrics.value.superResolutionRows[2]?.value

    form.superResolutionNumFrames = 2

    expect(model.metrics.value.superResolutionRows[2]?.value).toBe(before)
  })

  it('applies recurrent input frame edits to every selected media item before task start', () => {
    const { first, second } = seedSelectedPair((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
      workflow.superResolution.scaleFactor = 4
      workflow.superResolution.numFrames = 10
    })

    const { fields: form } = useEnhanceForm()
    form.superResolutionNumFrames = 5

    expect(first.workflowConfig.superResolution.numFrames).toBe(5)
    expect(second.workflowConfig.superResolution.numFrames).toBe(5)
  })

  it('persists all enhance page edits while applying them to every selected media item', () => {
    const { first, second, presetStore } = seedSelectedPair((workflow) => {
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
    })

    const { fields: form } = useEnhanceForm()
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

    for (const workflow of [
      first.workflowConfig,
      second.workflowConfig,
      presetStore.draftPreset.workflowConfig,
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
    }
  })

  it('persists process order while applying it to every selected media item', () => {
    const { first, second, presetStore } = seedSelectedPair((workflow) => {
      workflow.processOrder = 'super_resolution_then_interpolation'
    })

    const { fields: form } = useEnhanceForm()
    form.processOrder = 'frame_interpolation_then_super_resolution'

    expect(first.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(second.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(presetStore.draftPreset.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
  })

  it('applies EDVR fixed window defaults to every selected media item', () => {
    const { first, second, presetStore } = seedSelectedPair((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
      workflow.superResolution.scaleFactor = 4
      workflow.superResolution.numFrames = 10
    })

    const { fields: form } = useEnhanceForm()
    form.superResolutionAlgorithm = 'edvr'

    expect(first.workflowConfig.superResolution.algorithm).toBe('edvr')
    expect(first.workflowConfig.superResolution.numFrames).toBe(5)
    expect(second.workflowConfig.superResolution.algorithm).toBe('edvr')
    expect(second.workflowConfig.superResolution.numFrames).toBe(5)
    expect(presetStore.draftPreset.workflowConfig.superResolution.algorithm).toBe('edvr')
    expect(presetStore.draftPreset.workflowConfig.superResolution.numFrames).toBe(5)
  })

  it('projects selected model metrics for the active video', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    const item = createMediaItem('/video/clip.mp4', presetStore.draftPreset)
    mediaStore.appendItems([item])
    mediaStore.setItemInfo(item.id, {
      fps: 30,
      width: 1920,
      height: 1080,
      videoCodec: 'h264',
    })

    const { metrics } = useEnhanceForm()

    expect(metrics.value.interpolationRows[0].value).toBe('5.67M')
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
      fps: 27,
      width: 640,
      height: 288,
      videoCodec: 'h264',
    })

    const { metrics } = useEnhanceForm()

    expect(metrics.value.interpolationRows[2].value).toBe('1.96 GiB')
    expect(metrics.value.superResolutionRows[2].value).toBe('5.63 GiB')
    expect(metrics.value.combinedVramRows[0].value).toBe('5.63 GiB')
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
      fps: 27,
      width: 640,
      height: 288,
      videoCodec: 'h264',
    })

    const { metrics } = useEnhanceForm()

    expect(metrics.value.superResolutionRows[1].value).toBe('22.1 GFLOPs')
    expect(metrics.value.superResolutionRows[2].value).toBe('3.17 GiB')
  })
})
