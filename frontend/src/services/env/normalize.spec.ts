import { describe, expect, it } from 'vitest'

import { normalizeCheckResult } from './normalize'
import type { EnvironmentCheckResult } from '@/types/domain/env'

function baseResult(): EnvironmentCheckResult {
  return {
    type: 'check',
    ffmpeg: {
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { devices: [], adapters: [] },
    tensorBackends: {},
    rifeModel: {},
  }
}

describe('normalizeCheckResult', () => {
  it('normalizes engine metric overrides from snake_case payloads', () => {
    const result = normalizeCheckResult({
      ...baseResult(),
      interpolationAlgorithms: [
        {
          name: 'rife',
          tensorBackends: ['pytorch'],
          models: ['4.25'],
          modelDetails: [
            {
              name: '4.25',
              label: 'RIFE 4.25',
              metrics: {
                parameterCount: 1,
                parameterBytes: 4,
                gflopsPerMegapixel: 2,
                activationBytesPerMegapixel: 3,
                runtimeOverheadBytes: 5,
                inputModulo: 64,
                analysisStatus: 'ok',
                analysisNotes: [],
                engine_metrics: {
                  tensorrt: {
                    gflops_per_megapixel: 2,
                    activation_bytes_per_megapixel: 7,
                    runtime_overhead_bytes: 11,
                    runtime_frame_count: null,
                    input_modulo: 64,
                    analysis_status: 'partial',
                    analysis_notes: ['calibrated'],
                  },
                },
              } as EnvironmentCheckResult['interpolationAlgorithms'][number]['modelDetails'][number]['metrics'],
            },
          ],
        },
      ],
    })

    expect(result.interpolationAlgorithms?.[0].modelDetails?.[0].metrics.engineMetrics?.tensorrt).toMatchObject({
      gflopsPerMegapixel: 2,
      activationBytesPerMegapixel: 7,
      runtimeOverheadBytes: 11,
      inputModulo: 64,
      analysisStatus: 'partial',
      analysisNotes: ['calibrated'],
    })
  })

  it('normalizes and derives algorithm capability metadata from legacy payloads', () => {
    const result = normalizeCheckResult({
      ...baseResult(),
      superResolutionAlgorithms: [
        {
          name: 'legacy-paddlegan',
          tensorBackends: ['paddle'],
          models: ['x4'],
          scaleFactors: [4],
          defaultNumFrames: 10,
          sequenceMode: 'recurrent',
        },
        {
          name: 'legacy-edvr',
          tensorBackends: ['paddle'],
          models: ['x4'],
          scaleFactors: [4],
          defaultNumFrames: 5,
          sequence_mode: 'window',
        } as EnvironmentCheckResult['superResolutionAlgorithms'][number],
        {
          name: 'snake-case-metadata',
          tensorBackends: ['paddle'],
          models: ['x4'],
          scaleFactors: [4],
          family: 'paddlegan_vsr',
          fixed_scale_factor: 4,
          input_frame_mode: 'fixed_window',
        } as EnvironmentCheckResult['superResolutionAlgorithms'][number],
      ],
    })

    expect(result.superResolutionAlgorithms?.[0]).toMatchObject({
      family: 'paddlegan_vsr',
      fixedScaleFactor: 4,
      inputFrameMode: 'editable_chunk',
    })
    expect(result.superResolutionAlgorithms?.[1]).toMatchObject({
      family: 'paddlegan_vsr',
      fixedScaleFactor: 4,
      inputFrameMode: 'fixed_window',
      sequenceMode: 'window',
    })
    expect(result.superResolutionAlgorithms?.[2]).toMatchObject({
      family: 'paddlegan_vsr',
      fixedScaleFactor: 4,
      inputFrameMode: 'fixed_window',
    })
  })
})
