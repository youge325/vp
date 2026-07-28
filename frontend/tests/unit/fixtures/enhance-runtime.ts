import { createDefaultWorkflowConfigForEnvironment } from '@/services/preset/workflow-defaults'
import type { WorkflowConfig } from '@/types/protocol'
import {
  createAlgorithmInfo,
  createModelVariantInfo,
} from './environment'

export function createRuntimeWorkflow(): WorkflowConfig {
  const workflow = createDefaultWorkflowConfigForEnvironment(null)
  workflow.processOrder = 'super_resolution_then_interpolation'
  workflow.interpolation.enabled = true
  workflow.interpolation.scale = 1
  workflow.interpolation.fp16 = false
  workflow.superResolution.enabled = true
  workflow.superResolution.scaleFactor = 4
  workflow.superResolution.numFrames = 10
  return workflow
}

export function createRuntimeDetails() {
  return {
    interpolationDetail: createModelVariantInfo({
      name: '4.25',
      label: 'RIFE 4.25',
      metrics: {
        parameterCount: 1,
        parameterBytes: 4,
        gflopsPerMegapixel: 10,
        activationBytesPerMegapixel: 1000,
        runtimeOverheadBytes: 100,
        inputModulo: 1,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    }),
    superResolutionDetail: createModelVariantInfo({
      name: 'x4',
      label: 'EDVR',
      metrics: {
        parameterCount: 2,
        parameterBytes: 8,
        gflopsPerMegapixel: 20,
        activationBytesPerMegapixel: 2000,
        runtimeOverheadBytes: 200,
        runtimeFrameCount: 5,
        inputModulo: 1,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    }),
    fixedWindowAlgorithm: createAlgorithmInfo({
      name: 'edvr',
      family: 'paddlegan_vsr',
      tensorBackends: ['paddle'],
      models: ['x4'],
      fixedScaleFactor: 4,
      inputFrameMode: 'fixed_window',
      defaultNumFrames: 5,
    }),
  }
}
