import type {
  AlgorithmInfo,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
} from '@/types/protocol'

type EnvironmentOverrides = Omit<
  Partial<EnvironmentCheckResult>,
  'ffmpeg' | 'gpu' | 'tensorEngines' | 'interpolationAlgorithms' | 'superResolutionAlgorithms'
> & {
  ffmpeg?: Partial<EnvironmentCheckResult['ffmpeg']>
  gpu?: Partial<EnvironmentCheckResult['gpu']>
  tensorEngines?: Partial<EnvironmentCheckResult['tensorEngines']>
  interpolationAlgorithms?: Array<Partial<AlgorithmInfo>>
  superResolutionAlgorithms?: Array<Partial<AlgorithmInfo>>
}

export function createAlgorithmInfo(overrides: Partial<AlgorithmInfo> = {}): AlgorithmInfo {
  return {
    name: 'placeholder',
    family: 'onnx_super_resolution',
    tensorBackends: ['onnx'],
    models: [],
    onnxModels: [],
    modelDetails: [],
    onnxModelDetails: [],
    scaleFactors: [],
    fixedScaleFactor: null,
    defaultNumFrames: null,
    inputFrameMode: 'none',
    ...overrides,
  }
}

const ALGORITHM_FIELDS: Array<keyof AlgorithmInfo> = [
  'name',
  'family',
  'tensorBackends',
  'models',
  'onnxModels',
  'modelDetails',
  'onnxModelDetails',
  'scaleFactors',
  'fixedScaleFactor',
  'defaultNumFrames',
  'inputFrameMode',
]

function hydrateAlgorithmInfo(value: Partial<AlgorithmInfo>): AlgorithmInfo {
  return ALGORITHM_FIELDS.every((field) => Object.hasOwn(value, field))
    ? value as AlgorithmInfo
    : createAlgorithmInfo(value)
}

export function createEnvironmentResult(overrides: EnvironmentOverrides = {}): EnvironmentCheckResult {
  const result: EnvironmentCheckResult = {
    ffmpeg: {
      available: true,
      hwaccels: [],
      encoderProfiles: [],
      decoderProfiles: [],
    },
    gpu: { adapters: [] },
    tensorEngines: { pytorch: [], paddle: [], onnx: [] },
    interpolationAlgorithms: [],
    superResolutionAlgorithms: [],
    runtimeMode: 'external',
  }

  return {
    ...result,
    ...overrides,
    ffmpeg: { ...result.ffmpeg, ...overrides.ffmpeg },
    gpu: { ...result.gpu, ...overrides.gpu },
    tensorEngines: { ...result.tensorEngines, ...overrides.tensorEngines },
    interpolationAlgorithms: (overrides.interpolationAlgorithms ?? result.interpolationAlgorithms)
      .map(hydrateAlgorithmInfo),
    superResolutionAlgorithms: (overrides.superResolutionAlgorithms ?? result.superResolutionAlgorithms)
      .map(hydrateAlgorithmInfo),
  }
}

export function createEnvironmentPayload(
  result = createEnvironmentResult(),
  overrides: Partial<Omit<EnvironmentCheckPayload, 'result'>> = {},
): EnvironmentCheckPayload {
  return {
    result,
    source: 'probe',
    checkedAt: '2026-07-11T00:00:00Z',
    ...overrides,
  }
}
