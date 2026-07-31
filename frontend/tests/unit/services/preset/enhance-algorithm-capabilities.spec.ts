import { describe, expect, it } from 'vitest'

import {
  fixedRuntimeFrameCount,
  fixedSuperResolutionScaleFactor,
  isPaddleGanVsrAlgorithm,
  superResolutionInputFrameMode,
} from '@/services/preset/enhance-algorithm-capabilities'
import { createAlgorithmInfo } from '../../fixtures/environment'

describe('enhance algorithm capability rules', () => {
  it('classifies PaddleGAN VSR from explicit family metadata', () => {
    expect(
      isPaddleGanVsrAlgorithm(createAlgorithmInfo({
        name: 'custom-vsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        inputFrameMode: 'editable_chunk',
      })),
    ).toBe(true)
  })

  it('does not infer a family when the protocol reports another family', () => {
    expect(
      isPaddleGanVsrAlgorithm(createAlgorithmInfo({
        name: 'onnx-vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
      })),
    ).toBe(false)
  })

  it('resolves input frame mode and fixed values from metadata', () => {
    const algorithm = createAlgorithmInfo({
      name: 'fixed-window-vsr',
      family: 'paddlegan_vsr',
      tensorBackends: ['paddle'],
      models: ['x4'],
      fixedScaleFactor: 4,
      inputFrameMode: 'fixed_window',
      defaultNumFrames: 7,
      modelDetails: [
        {
          name: 'x4',
          label: 'x4',
          metrics: {
            runtimeFrameCount: 5,
            analysisStatus: 'ok',
            analysisNotes: [],
          },
        },
      ],
    })

    expect(superResolutionInputFrameMode(algorithm)).toBe('fixed_window')
    expect(fixedRuntimeFrameCount(algorithm)).toBe(5)
    expect(fixedSuperResolutionScaleFactor(algorithm)).toBe(4)
  })
})
