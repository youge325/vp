import { describe, expect, it } from 'vitest'

import { createDefaultWorkflowConfig } from './defaults'

describe('createDefaultWorkflowConfig PaddleGAN SR fields', () => {
  it('creates independent super-resolution runtime fields', () => {
    const workflow = createDefaultWorkflowConfig()

    expect(workflow.superResolution.tensorBackend).toBe('onnx')
    expect(workflow.superResolution.engine).toBe('cuda')
    expect(workflow.superResolution.numFrames).toBe(10)
    expect(workflow.superResolution.autoDownloadWeights).toBe(true)
  })
})
