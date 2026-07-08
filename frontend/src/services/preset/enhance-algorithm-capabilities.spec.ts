import { describe, expect, it } from 'vitest'

import {
  fixedRuntimeFrameCount,
  fixedSuperResolutionScaleFactor,
  isPaddleGanVsrAlgorithm,
  superResolutionInputFrameMode,
} from './enhance-algorithm-capabilities'

describe('enhance algorithm capability rules', () => {
  it('classifies PaddleGAN VSR from explicit family metadata', () => {
    expect(
      isPaddleGanVsrAlgorithm({
        name: 'custom-vsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
      }),
    ).toBe(true)
  })

  it('keeps legacy metadata fallback for old cached environment payloads', () => {
    expect(
      isPaddleGanVsrAlgorithm({
        name: 'legacy-vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        sequenceMode: 'recurrent',
        scaleFactors: [4],
      }),
    ).toBe(true)
  })

  it('resolves input frame mode and fixed values from metadata', () => {
    const algorithm = {
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
    } as const

    expect(superResolutionInputFrameMode(algorithm)).toBe('fixed_window')
    expect(fixedRuntimeFrameCount(algorithm)).toBe(5)
    expect(fixedSuperResolutionScaleFactor(algorithm)).toBe(4)
  })
})
