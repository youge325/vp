import { describe, expect, it } from 'vitest'

import { buildEnhanceViewModel } from '@/services/preset/enhance-view-model'
import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import type { AlgorithmInfo } from '@/types/protocol'
import {
  createEdvrAlgorithm,
  createPpmsvsrAlgorithm,
  createRifeAlgorithm,
} from '../../fixtures/environment'

const rife: AlgorithmInfo = createRifeAlgorithm()
const ppmsvsr: AlgorithmInfo = createPpmsvsrAlgorithm()
const edvr: AlgorithmInfo = createEdvrAlgorithm()

describe('enhance view-model rules', () => {
  it('resolves selected models and estimates SR-to-interpolation runtime rows', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.processOrder = 'super_resolution_then_interpolation'
    workflow.interpolation.enabled = true
    workflow.interpolation.tensorBackend = 'pytorch'
    workflow.interpolation.engine = 'cuda'
    workflow.interpolation.algorithm = 'rife'
    workflow.interpolation.model = '4.25'
    workflow.interpolation.fp16 = false
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'cuda'
    workflow.superResolution.algorithm = 'ppmsvsr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 10

    const model = buildEnhanceViewModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: ppmsvsr,
    })

    expect(model.currentInterpolationModelDetail?.name).toBe('4.25')
    expect(model.interpolationInputDimensions).toEqual({ width: 2560, height: 1152 })
    expect(model.interpolationRuntimeEstimate?.effectiveHeight).toBe(1152)
    expect(model.interpolationMetricRows[2].value).toBe('1.96 GiB')
    expect(model.superResolutionMetricRows[2].value).toBe('5.63 GiB')
    expect(model.combinedVramMetricRows[0].value).toBe('5.63 GiB')
    expect(model.effectiveSuperResolutionNumFrames).toBe(10)
  })

  it('uses fixed-window SR runtime frames instead of stale editable workflow value', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'cuda'
    workflow.superResolution.algorithm = 'edvr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 10

    const model = buildEnhanceViewModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: edvr,
    })

    expect(model.isPaddleGanSuperResolution).toBe(true)
    expect(model.isSuperResolutionInputFramesEditable).toBe(false)
    expect(model.superResolutionFixedWindowRows).toEqual([
      { label: '邻帧窗口', value: '5 帧（固定）' },
    ])
    expect(model.superResolutionMetricRows).toEqual(buildEnhanceViewModel({
      workflow: {
        ...workflow,
        superResolution: { ...workflow.superResolution, numFrames: 2 },
      },
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: edvr,
    }).superResolutionMetricRows)
    expect(model.effectiveSuperResolutionNumFrames).toBe(5)
  })

  it('uses selected TensorRT engine metrics for super-resolution estimates', () => {
    const workflow = createDefaultWorkflowConfigForEnvironment(null)
    workflow.superResolution.enabled = true
    workflow.superResolution.tensorBackend = 'paddle'
    workflow.superResolution.engine = 'tensorrt'
    workflow.superResolution.algorithm = 'ppmsvsr'
    workflow.superResolution.scaleFactor = 4
    workflow.superResolution.numFrames = 5

    const model = buildEnhanceViewModel({
      workflow,
      activeVideoDimensions: { width: 640, height: 288 },
      currentInterpolationAlgorithm: rife,
      currentSuperResolutionAlgorithm: ppmsvsr,
    })

    expect(model.superResolutionMetricRows[1].value).toBe('22.1 GFLOPs')
    expect(model.superResolutionMetricRows[2].value).toBe('3.17 GiB')
  })
})
