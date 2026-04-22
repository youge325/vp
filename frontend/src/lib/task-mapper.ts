import { PROCESS_ORDER_LABELS, WORKFLOW_LABELS } from '@/lib/workflow'
import type {
  ProcessOrder,
  TaskRequest,
  WorkbenchStateSnapshot,
  WorkflowMode,
} from '@/types'

export function resolvePrimaryMode(snapshot: WorkbenchStateSnapshot): WorkflowMode {
  if (snapshot.workflow.enableInterpolation) {
    return 'frame_interpolation'
  }

  if (snapshot.workflow.enableSuperResolution) {
    return 'super_resolution'
  }

  if (snapshot.anime.enabled) {
    return 'anime_optimization'
  }

  return 'format_conversion'
}

export function supportsCombinedProcessing(mode: WorkflowMode): boolean {
  return mode === 'frame_interpolation' || mode === 'super_resolution'
}

export function normalizeProcessOrder(order: ProcessOrder): string {
  return PROCESS_ORDER_LABELS[order]
}

export function buildTaskRequest(snapshot: WorkbenchStateSnapshot): TaskRequest {
  const algorithm = resolvePrimaryMode(snapshot)
  const enableInterpolation = snapshot.workflow.enableInterpolation
  const enableSuperResolution = snapshot.workflow.enableSuperResolution
  const outputFps = enableInterpolation
    ? snapshot.workflow.fpsMode === 'target'
      ? snapshot.interpolation.targetFps
      : snapshot.interpolation.multi * (snapshot.source.info?.fps ?? 30)
    : snapshot.source.info?.fps ?? snapshot.interpolation.targetFps

  return {
    inputPath: snapshot.source.inputPath.trim(),
    algorithm,
    outputPath: snapshot.output.outputPath.trim() || undefined,
    outputDir: snapshot.output.outputDir.trim() || undefined,
    tempDir: snapshot.output.tempDir.trim() || undefined,
    fps: outputFps,
    fpsMode: snapshot.workflow.fpsMode,
    targetFps:
      enableInterpolation && snapshot.workflow.fpsMode === 'target'
        ? snapshot.interpolation.targetFps
        : undefined,
    codec: snapshot.encode.codec,
    crf: snapshot.encode.crf,
    preset: snapshot.encode.preset,
    backend: snapshot.interpolation.tensorBackend,
    multi: snapshot.interpolation.multi,
    model: snapshot.interpolation.model,
    scale: snapshot.interpolation.scale,
    fp16: snapshot.interpolation.fp16,
    enableInterpolation,
    enableSuperResolution,
    processOrder: snapshot.workflow.processOrder,
    srScaleFactor: snapshot.superResolution.scaleFactor,
    srAlgorithm: snapshot.superResolution.algorithm,
  }
}

export interface SummarySection {
  title: string
  lines: string[]
}

export function buildSummarySections(snapshot: WorkbenchStateSnapshot): SummarySection[] {
  const sourceInfo = snapshot.source.info
  const primaryMode = resolvePrimaryMode(snapshot)
  const runtimeMode = snapshot.env.checkResult?.runtime?.mode ?? '未检查'
  const gpuLabel = snapshot.env.checkResult?.gpu?.devices?.[0] ?? '未检测'
  const taskLabel =
    snapshot.task.status === 'running'
      ? `${snapshot.task.percent.toFixed(1)}%`
      : WORKFLOW_LABELS[primaryMode]

  const enhanceLines = [
    snapshot.workflow.enableInterpolation ? '补帧 On' : '补帧 Off',
    snapshot.workflow.enableSuperResolution ? '超分 On' : '超分 Off',
    snapshot.anime.enabled ? '动漫 On' : '动漫 Off',
  ]

  if (snapshot.workflow.enableInterpolation && snapshot.workflow.enableSuperResolution) {
    enhanceLines.push(normalizeProcessOrder(snapshot.workflow.processOrder))
  }

  return [
    {
      title: '素材',
      lines: [
        snapshot.source.inputPath || '未选择',
        sourceInfo
          ? `${sourceInfo.width}×${sourceInfo.height} · ${formatNumber(sourceInfo.fps)} FPS`
          : '未读取',
      ],
    },
    {
      title: '环境',
      lines: [
        runtimeMode,
        snapshot.env.checkResult?.ffmpeg?.available ? 'FFmpeg Ready' : 'FFmpeg Idle',
        gpuLabel,
      ],
    },
    {
      title: '增强',
      lines: enhanceLines,
    },
    {
      title: '编码',
      lines: [
        snapshot.format.container.toUpperCase(),
        snapshot.encode.codec,
        `CRF ${snapshot.encode.crf} · ${snapshot.encode.preset}`,
      ],
    },
    {
      title: '任务',
      lines: [
        snapshot.task.status,
        taskLabel,
        snapshot.task.stage || '等待启动',
      ],
    },
  ]
}

export function formatNumber(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.01) {
    return `${Math.round(value)}`
  }

  return value.toFixed(2).replace(/\.?0+$/, '')
}
