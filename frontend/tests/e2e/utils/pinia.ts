import { withPiniaState, withPiniaStore } from './wdio-tauri'

type OperationIssueScope = 'input' | 'encode' | 'task' | 'preset' | 'environment'

interface OperationIssueError {
  message: string
  code?: string
  details?: unknown
}

interface OperationIssuePayload {
  scope: OperationIssueScope
  error: OperationIssueError
}

export async function setOperationIssue(
  scope: OperationIssueScope,
  error: OperationIssueError,
): Promise<boolean> {
  return await withPiniaStore('issue', (store, _win, payload: OperationIssuePayload) => {
    const setIssue = store.setIssue as ((scope: OperationIssueScope, error: OperationIssueError) => void) | undefined
    if (!setIssue) {
      return false
    }
    setIssue(payload.scope, { details: null, ...payload.error })
    return true
  }, { scope, error })
}

export async function clearOperationIssue(scope?: OperationIssueScope): Promise<void> {
  await withPiniaStore('issue', (store, _win, activeScope: OperationIssueScope | undefined) => {
    const clearIssue = store.clearIssue as ((scope?: OperationIssueScope) => void) | undefined
    if (clearIssue) {
      clearIssue(activeScope)
    }
  }, scope)
}

export async function setDeterministicEnhanceMetricState(): Promise<boolean> {
  return await withPiniaState((state) => {
    const envStore = state.env as {
      env?: {
        checkResult?: unknown
        isChecking?: boolean
      }
    } | undefined
    const presetStore = state.preset as {
      draftPreset?: {
        decodeConfig: unknown
        workflowConfig: {
          interpolation: Record<string, unknown>
          superResolution: Record<string, unknown>
        }
        encodeConfig: unknown
        outputConfig: unknown
      }
    } | undefined
    const mediaStore = state.media as {
      mediaItems?: unknown[]
      activeItemId?: string | null
    } | undefined
    const draft = presetStore?.draftPreset
    if (!envStore?.env || !draft || !mediaStore) {
      return false
    }

    const metric = (
      parameterCount: number,
      gflopsPerMegapixel: number,
      activationBytesPerMegapixel: number,
    ) => ({
      parameterCount,
      parameterBytes: parameterCount * 4,
      gflopsPerMegapixel,
      activationBytesPerMegapixel,
      runtimeOverheadBytes: 32_000_000,
      runtimeFrameCount: null,
      inputModulo: 8,
      analysisStatus: 'ok',
      analysisNotes: [],
      engineMetrics: {},
    })

    envStore.env.checkResult = {
      ffmpeg: {
        available: true,
        hwaccels: [],
        encoderProfiles: [],
        decoderProfiles: [],
      },
      gpu: { adapters: [] },
      tensorEngines: { pytorch: [], paddle: [], onnx: [] },
      interpolationAlgorithms: [{
        name: 'rife-e2e',
        family: 'rife',
        tensorBackends: ['pytorch'],
        models: ['metric-interpolation'],
        onnxModels: [],
        modelDetails: [{
          name: 'metric-interpolation',
          label: 'Metric Interpolation',
          metrics: metric(1_250_000, 10, 120_000_000),
        }],
        onnxModelDetails: [],
        scaleFactors: [],
        modelLicense: null,
        defaultNumFrames: null,
        inputFrameMode: 'none',
      }],
      superResolutionAlgorithms: [{
        name: 'sr-e2e',
        family: 'onnx_super_resolution',
        tensorBackends: ['onnx'],
        models: [],
        onnxModels: ['metric-super-resolution.onnx'],
        modelDetails: [],
        onnxModelDetails: [{
          name: 'metric-super-resolution.onnx',
          label: 'Metric Super Resolution',
          metrics: metric(7_500_000, 20, 240_000_000),
        }],
        scaleFactors: [2],
        modelLicense: null,
        defaultNumFrames: null,
        inputFrameMode: 'none',
      }],
      runtimeMode: 'external',
    }
    envStore.env.isChecking = false

    const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
    const workflow = clone(draft.workflowConfig)
    Object.assign(workflow.interpolation, {
      enabled: true,
      algorithm: 'rife-e2e',
      model: 'metric-interpolation',
      onnxModel: '',
      tensorBackend: 'pytorch',
      engine: 'cuda',
    })
    Object.assign(workflow.superResolution, {
      enabled: true,
      algorithm: 'sr-e2e',
      onnxModel: 'metric-super-resolution.onnx',
      tensorBackend: 'onnx',
      engine: 'cuda',
      scaleFactor: 2,
    })

    const itemId = 'metric-preview'
    mediaStore.mediaItems = [{
      id: itemId,
      displayName: 'metric-preview.mp4',
      inputPath: 'C:/tmp/metric-preview.mp4',
      selected: false,
      inspecting: false,
      info: {
        width: 640,
        height: 360,
        fps: 30,
        videoCodec: 'h264',
      },
      decodeConfig: clone(draft.decodeConfig),
      workflowConfig: workflow,
      encodeConfig: clone(draft.encodeConfig),
      outputConfig: clone(draft.outputConfig),
    }]
    mediaStore.activeItemId = itemId
    return true
  })
}

export async function setDeterministicRealRawVsrState(scaleFactor: 2 | 3 | 4 = 2): Promise<boolean> {
  return await withPiniaState((state, _win, selectedScale: 2 | 3 | 4) => {
    const envStore = state.env as {
      env?: { checkResult?: unknown; isChecking?: boolean }
    } | undefined
    const presetStore = state.preset as {
      draftPreset?: {
        workflowConfig: {
          interpolation: Record<string, unknown>
          superResolution: Record<string, unknown>
        }
      }
    } | undefined
    const mediaStore = state.media as {
      mediaItems?: unknown[]
      activeItemId?: string | null
    } | undefined
    const draft = presetStore?.draftPreset
    if (!envStore?.env || !draft || !mediaStore) {
      return false
    }

    const metric = (name: string, scale: number, parameters: number) => ({
      name,
      label: `Real-RawVSR BasicVSR ${scale}x`,
      metrics: {
        parameterCount: parameters,
        parameterBytes: parameters * 4,
        gflopsPerMegapixel: null,
        activationBytesPerMegapixel: null,
        runtimeOverheadBytes: null,
        runtimeFrameCount: null,
        inputModulo: 1,
        analysisStatus: 'partial',
        analysisNotes: ['PyTorch CUDA sequence inference; actual memory depends on the logical frame chunk.'],
        engineMetrics: {},
      },
    })
    envStore.env.checkResult = {
      ffmpeg: { available: true, hwaccels: [], encoderProfiles: [], decoderProfiles: [] },
      gpu: { adapters: [{ name: 'NVIDIA GeForce RTX', vendor: 'nvidia' }] },
      tensorEngines: { pytorch: ['cuda'], paddle: [], onnx: [] },
      interpolationAlgorithms: [],
      superResolutionAlgorithms: [{
        name: 'real-rawvsr-basicvsr',
        family: 'pytorch_vsr',
        tensorBackends: ['pytorch'],
        models: ['x2', 'x3', 'x4'],
        onnxModels: [],
        modelDetails: [
          metric('x2', 2, 6_143_599),
          metric('x3', 3, 6_328_239),
          metric('x4', 4, 6_291_311),
        ],
        onnxModelDetails: [],
        scaleFactors: [2, 3, 4],
        modelLicense: {
          spdxId: 'CC-BY-NC-SA-4.0',
          usage: 'non_commercial',
          sourceUrl: 'https://github.com/zmzhang1998/Real-RawVSR',
        },
        defaultNumFrames: 10,
        inputFrameMode: 'editable_chunk',
      }],
      runtimeMode: 'bundled',
    }
    envStore.env.isChecking = false
    Object.assign(draft.workflowConfig.interpolation, { enabled: false })
    Object.assign(draft.workflowConfig.superResolution, {
      enabled: true,
      algorithm: 'real-rawvsr-basicvsr',
      tensorBackend: 'pytorch',
      engine: 'cuda',
      scaleFactor: selectedScale,
      numFrames: 10,
      onnxModel: '',
    })
    mediaStore.mediaItems = []
    mediaStore.activeItemId = null
    return true
  }, scaleFactor)
}
