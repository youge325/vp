import { withPiniaState } from './wdio-tauri'

interface EnvironmentFixture {
  encoderProfiles?: unknown[]
  decoderProfiles?: unknown[]
  decodeConfig?: Record<string, unknown>
  encodeConfig?: Record<string, unknown>
}

export async function installEnvironmentFixture(
  fixture: EnvironmentFixture,
): Promise<boolean> {
  return await withPiniaState((state, _win, payload: EnvironmentFixture) => {
    const env = (state.env as { env?: Record<string, unknown> } | undefined)?.env
    const draft = (state.preset as {
      draftPreset?: Record<string, unknown>
    } | undefined)?.draftPreset
    if (!env || !draft) {
      return false
    }
    env.checkResult = {
      ffmpeg: {
        available: true,
        hwaccels: payload.decoderProfiles?.length ? ['cuda', 'qsv', 'd3d11va'] : [],
        encoderProfiles: payload.encoderProfiles ?? [],
        decoderProfiles: payload.decoderProfiles ?? [],
      },
      gpu: { adapters: [] },
      tensorEngines: { pytorch: [], paddle: [], onnx: [] },
      interpolationAlgorithms: [],
      superResolutionAlgorithms: [],
      runtimeMode: 'external',
    }
    if (payload.decodeConfig) {
      draft.decodeConfig = payload.decodeConfig
    }
    if (payload.encodeConfig) {
      draft.encodeConfig = payload.encodeConfig
    }
    return true
  }, fixture)
}
