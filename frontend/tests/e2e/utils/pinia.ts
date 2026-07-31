import { withPiniaState } from './wdio-tauri'

type OperationIssueScope = 'input' | 'encode' | 'task' | 'preset'

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
  return await withPiniaState((state, _win, payload: OperationIssuePayload) => {
    const issueStore = state.issue as { operationIssue?: unknown } | undefined
    if (!issueStore) {
      return false
    }
    issueStore.operationIssue = {
      scope: payload.scope,
      error: {
        details: null,
        ...payload.error,
      },
    }
    return true
  }, { scope, error })
}

export async function clearOperationIssue(): Promise<void> {
  await withPiniaState((state) => {
    const issueStore = state.issue as { operationIssue?: unknown } | undefined
    if (issueStore) {
      issueStore.operationIssue = null
    }
  })
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
        fixedScaleFactor: null,
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
        fixedScaleFactor: 2,
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
