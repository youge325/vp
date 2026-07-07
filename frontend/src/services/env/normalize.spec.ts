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
})
