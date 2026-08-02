import type {
  AlgorithmInfo,
  CapabilityOptionSpec,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
  ModelVariantInfo,
} from '@/types/protocol'
import type {
  ModelEngineMetricInfo,
  ModelMetricInfo,
} from '@/types/generated/contracts'

type ModelEngineMetricOverrides = Partial<ModelEngineMetricInfo>
export type ModelMetricOverrides = Omit<Partial<ModelMetricInfo>, 'engineMetrics'> & {
  engineMetrics?: { [key: string]: ModelEngineMetricOverrides | undefined }
}

function createCapabilityOption(
  name: string,
  defaultValue: string,
  choices: Array<{ label: string; value: string }> = [],
): CapabilityOptionSpec {
  return {
    name,
    label: name,
    type: choices.length ? 'choice' : 'string',
    defaultValue,
    choices,
    min: null,
    max: null,
  }
}
type ModelVariantOverrides =
  | ModelVariantInfo
  | (Omit<Partial<ModelVariantInfo>, 'metrics'> & { metrics?: ModelMetricOverrides })
type AlgorithmOverrides =
  | AlgorithmInfo
  | (
    & Omit<Partial<AlgorithmInfo>, 'modelDetails' | 'onnxModelDetails'>
    & {
      modelDetails?: ModelVariantOverrides[]
      onnxModelDetails?: ModelVariantOverrides[]
    }
  )
type EnvironmentOverrides = Omit<
  Partial<EnvironmentCheckResult>,
  'ffmpeg' | 'gpu' | 'tensorEngines' | 'interpolationAlgorithms' | 'superResolutionAlgorithms'
> & {
  ffmpeg?: Partial<EnvironmentCheckResult['ffmpeg']>
  gpu?: Partial<EnvironmentCheckResult['gpu']>
  tensorEngines?: Partial<EnvironmentCheckResult['tensorEngines']>
  interpolationAlgorithms?: AlgorithmOverrides[]
  superResolutionAlgorithms?: AlgorithmOverrides[]
}

function createModelEngineMetricInfo(
  overrides: ModelEngineMetricOverrides = {},
): ModelEngineMetricInfo {
  return {
    gflopsPerMegapixel: null,
    activationBytesPerMegapixel: null,
    runtimeOverheadBytes: null,
    runtimeFrameCount: null,
    inputModulo: null,
    analysisStatus: 'unknown',
    analysisNotes: [],
    ...overrides,
  }
}

export function createModelMetricInfo(overrides: ModelMetricOverrides = {}): ModelMetricInfo {
  const engineMetrics = Object.fromEntries(
    Object.entries(overrides.engineMetrics ?? {}).map(([engine, metrics]) => [
      engine,
      createModelEngineMetricInfo(metrics),
    ]),
  )
  return {
    parameterCount: null,
    parameterBytes: null,
    gflopsPerMegapixel: null,
    activationBytesPerMegapixel: null,
    runtimeOverheadBytes: null,
    runtimeFrameCount: null,
    inputModulo: null,
    analysisStatus: 'unknown',
    analysisNotes: [],
    ...overrides,
    engineMetrics,
  }
}

export function createModelVariantInfo(overrides: ModelVariantOverrides = {}): ModelVariantInfo {
  return {
    name: 'placeholder',
    label: 'Placeholder',
    ...overrides,
    metrics: createModelMetricInfo(overrides.metrics),
  }
}

export function createRifeModelDetail(
  overrides: ModelMetricOverrides = {},
  identity: Partial<Pick<ModelVariantInfo, 'name' | 'label'>> = {},
): ModelVariantInfo {
  return createModelVariantInfo({
    name: '4.25',
    label: 'RIFE 4.25',
    ...identity,
    metrics: {
      parameterCount: 5670892,
      parameterBytes: 22683568,
      gflopsPerMegapixel: 18.5,
      activationBytesPerMegapixel: 694800000,
      runtimeOverheadBytes: 38000000,
      inputModulo: 64,
      analysisStatus: 'ok',
      analysisNotes: [],
      ...overrides,
    },
  })
}

export function createAlgorithmInfo(overrides: AlgorithmOverrides = {}): AlgorithmInfo {
  return {
    name: 'placeholder',
    family: 'onnx_super_resolution',
    tensorBackends: ['onnx'],
    models: [],
    onnxModels: [],
    scaleFactors: [],
    modelLicense: null,
    defaultNumFrames: null,
    inputFrameMode: 'none',
    ...overrides,
    modelDetails: (overrides.modelDetails ?? []).map(createModelVariantInfo),
    onnxModelDetails: (overrides.onnxModelDetails ?? []).map(createModelVariantInfo),
  }
}

function hydrateAlgorithmInfo(value: AlgorithmOverrides): AlgorithmInfo {
  return createAlgorithmInfo(value)
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

export function createEncodingEnvironment(): EnvironmentCheckResult {
  return createEnvironmentResult({
    ffmpeg: {
      available: true,
      hwaccels: [],
      decoderProfiles: [],
      encoderProfiles: [
        {
          name: 'libx265',
          label: 'x265',
          family: 'software',
          codec: 'hevc',
          available: true,
          hardwareDevices: [],
          options: [createCapabilityOption('preset', 'medium')],
          rateControlModes: [{ mode: 'crf', label: 'CRF', defaultValue: 18, unit: 'CRF' }],
        },
        {
          name: 'hevc_nvenc',
          label: 'NVENC H.265',
          family: 'nvidia',
          codec: 'hevc',
          available: true,
          hardwareDevices: [],
          options: [
            createCapabilityOption('preset', 'p5'),
            createCapabilityOption('tune', 'hq'),
          ],
          rateControlModes: [{ mode: 'cq', label: 'CQ', defaultValue: 24, unit: 'CQ' }],
        },
      ],
    },
  })
}

export function createRifeAlgorithm(): AlgorithmInfo {
  return createAlgorithmInfo({
    name: 'rife',
    family: 'rife',
    tensorBackends: ['pytorch', 'onnx'],
    models: ['4.25'],
    onnxModels: ['rife_v4.25.onnx'],
    modelDetails: [createRifeModelDetail()],
    onnxModelDetails: [
      createRifeModelDetail({}, {
        name: 'rife_v4.25.onnx',
        label: 'rife_v4.25.onnx',
      }),
    ],
  })
}

export function createEdvrAlgorithm(): AlgorithmInfo {
  return createAlgorithmInfo({
    name: 'edvr',
    family: 'paddlegan_vsr',
    tensorBackends: ['paddle'],
    models: ['x4'],
    scaleFactors: [4],
    modelLicense: null,
    inputFrameMode: 'fixed_window',
    defaultNumFrames: 5,
    modelDetails: [{
      name: 'x4',
      label: 'EDVR',
      metrics: {
        parameterCount: 20633827,
        parameterBytes: 82535308,
        gflopsPerMegapixel: 240,
        activationBytesPerMegapixel: 1000,
        runtimeOverheadBytes: 100,
        runtimeFrameCount: 5,
        inputModulo: 4,
        analysisStatus: 'ok',
        analysisNotes: [],
      },
    }],
  })
}

export function createPpmsvsrAlgorithm(): AlgorithmInfo {
  return createAlgorithmInfo({
    name: 'ppmsvsr',
    family: 'paddlegan_vsr',
    tensorBackends: ['paddle'],
    models: ['x4'],
    scaleFactors: [4],
    modelLicense: null,
    inputFrameMode: 'editable_chunk',
    defaultNumFrames: 10,
    modelDetails: [{
      name: 'x4',
      label: 'PP-MSVSR',
      metrics: {
        parameterCount: 1453607,
        parameterBytes: 5814428,
        gflopsPerMegapixel: 120,
        activationBytesPerMegapixel: 1981031424,
        runtimeOverheadBytes: 2391117604,
        runtimeFrameCount: null,
        inputModulo: 4,
        analysisStatus: 'ok',
        analysisNotes: [],
        engineMetrics: {
          tensorrt: {
            gflopsPerMegapixel: 120,
            activationBytesPerMegapixel: 3688504346,
            runtimeOverheadBytes: 0,
            runtimeFrameCount: null,
            analysisStatus: 'ok',
            analysisNotes: ['TensorRT calibrated'],
          },
        },
      },
    }],
  })
}

function createRealRawVsrAlgorithm(
  name: string,
  displayName: string,
  inputFrameMode: AlgorithmInfo['inputFrameMode'],
  defaultNumFrames: number,
  parameterCounts: readonly [number, number, number],
): AlgorithmInfo {
  return createAlgorithmInfo({
    name,
    family: 'pytorch_vsr',
    tensorBackends: ['pytorch'],
    models: ['x2', 'x3', 'x4'],
    scaleFactors: [2, 3, 4],
    modelLicense: {
      spdxId: 'CC-BY-NC-SA-4.0',
      usage: 'non_commercial',
      sourceUrl: 'https://github.com/zmzhang1998/Real-RawVSR',
    },
    inputFrameMode,
    defaultNumFrames,
    modelDetails: [2, 3, 4].map((scale, index) => ({
      name: `x${scale}`,
      label: `${displayName} ${scale}x`,
      metrics: {
        parameterCount: parameterCounts[index] ?? null,
        parameterBytes: (parameterCounts[index] ?? 0) * 4,
        gflopsPerMegapixel: null,
        activationBytesPerMegapixel: null,
        runtimeOverheadBytes: null,
        runtimeFrameCount: defaultNumFrames,
        inputModulo: inputFrameMode === 'fixed_window' ? 16 : null,
        analysisStatus: 'partial',
        analysisNotes: [],
        engineMetrics: {},
      },
    })),
  })
}

export function createRealRawVsrBasicVsrAlgorithm(): AlgorithmInfo {
  return createRealRawVsrAlgorithm(
    'real-rawvsr-basicvsr',
    'Real-RawVSR BasicVSR',
    'editable_chunk',
    10,
    [6_143_599, 6_328_239, 6_291_311],
  )
}

export function createEnhanceEnvironment(): EnvironmentCheckResult {
  return createEnvironmentResult({
    tensorEngines: {
      pytorch: ['cuda', 'tensorrt'],
      paddle: ['cuda', 'tensorrt'],
      onnx: ['cuda', 'tensorrt'],
    },
    interpolationAlgorithms: [
      createRifeAlgorithm(),
      createAlgorithmInfo({
        name: 'rife-lite',
        family: 'rife',
        tensorBackends: ['pytorch'],
        models: ['lite'],
      }),
      createAlgorithmInfo({
        name: 'onnx-only',
        family: 'rife',
        tensorBackends: ['onnx'],
        models: ['onnx'],
        onnxModels: ['onnx-only.onnx'],
      }),
    ],
    superResolutionAlgorithms: [
      createRealRawVsrBasicVsrAlgorithm(),
      createRealRawVsrAlgorithm(
        'real-rawvsr-edvr',
        'Real-RawVSR EDVR',
        'fixed_window',
        5,
        [3_152_419, 3_337_059, 3_300_131],
      ),
      createRealRawVsrAlgorithm(
        'real-rawvsr-tdan',
        'Real-RawVSR TDAN',
        'fixed_window',
        5,
        [2_137_251, 2_321_891, 2_284_963],
      ),
      createRealRawVsrAlgorithm(
        'real-rawvsr-toflow',
        'Real-RawVSR TOFlow',
        'fixed_window',
        5,
        [1_375_969, 1_375_969, 1_375_969],
      ),
      createAlgorithmInfo({
        name: 'placeholder',
        tensorBackends: ['onnx'],
        onnxModels: ['sr_x2.onnx'],
      }),
      createPpmsvsrAlgorithm(),
      createEdvrAlgorithm(),
      createAlgorithmInfo({
        name: 'custom-vsr',
        family: 'paddlegan_vsr',
        tensorBackends: ['paddle'],
        models: ['x4'],
        scaleFactors: [4],
        modelLicense: null,
        inputFrameMode: 'editable_chunk',
        defaultNumFrames: 8,
      }),
      ...['ppmsvsr-large', 'basicvsr', 'iconvsr', 'basicvsr-plus-plus'].map(name =>
        createAlgorithmInfo({
          name,
          family: 'paddlegan_vsr',
          tensorBackends: ['paddle'],
          models: ['x4'],
          scaleFactors: [4],
          modelLicense: null,
          inputFrameMode: 'editable_chunk',
          defaultNumFrames: 10,
        }),
      ),
    ],
    runtimeMode: 'bundled',
  })
}
