import {
  PROCESS_ORDER_LABELS,
  WORKFLOW_LABELS,
} from '@/lib/workflow'
import type {
  ProcessOrder,
  TaskRequest,
  WorkbenchStateSnapshot,
  WorkflowMode,
} from '@/types'

export function supportsCombinedProcessing(mode: WorkflowMode): boolean {
  return mode === 'frame_interpolation' || mode === 'super_resolution'
}

export function resolveAlgorithm(snapshot: WorkbenchStateSnapshot): WorkflowMode {
  const { workflow } = snapshot

  if (!supportsCombinedProcessing(workflow.primaryMode)) {
    return workflow.primaryMode
  }

  if (workflow.enableInterpolation) {
    return 'frame_interpolation'
  }

  return 'super_resolution'
}

export function normalizeProcessOrder(order: ProcessOrder): string {
  return PROCESS_ORDER_LABELS[order]
}

export function buildTaskRequest(snapshot: WorkbenchStateSnapshot): TaskRequest {
  const algorithm = resolveAlgorithm(snapshot)
  const combined = supportsCombinedProcessing(snapshot.workflow.primaryMode)
  const enableInterpolation = combined && snapshot.workflow.enableInterpolation
  const enableSuperResolution = combined && snapshot.workflow.enableSuperResolution

  return {
    inputPath: snapshot.source.inputPath.trim(),
    algorithm,
    outputPath: snapshot.output.outputPath.trim() || undefined,
    outputDir: snapshot.output.outputDir.trim() || undefined,
    tempDir: snapshot.output.tempDir.trim() || undefined,
    fps:
      snapshot.workflow.fpsMode === 'target'
        ? snapshot.interpolation.targetFps
        : snapshot.interpolation.multi * (snapshot.source.info?.fps ?? 30),
    fpsMode: snapshot.workflow.fpsMode,
    targetFps:
      snapshot.workflow.fpsMode === 'target' ? snapshot.interpolation.targetFps : undefined,
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
  const workflowName = WORKFLOW_LABELS[snapshot.workflow.primaryMode]
  const strategyLines = [workflowName]

  if (supportsCombinedProcessing(snapshot.workflow.primaryMode)) {
    strategyLines.push(
      snapshot.workflow.enableInterpolation ? '补帧已启用' : '补帧未启用',
      snapshot.workflow.enableSuperResolution ? '超分已启用' : '超分未启用',
      normalizeProcessOrder(snapshot.workflow.processOrder),
    )
  }

  return [
    {
      title: '素材',
      lines: [
        snapshot.source.inputPath || '未选择输入素材',
        sourceInfo
          ? `${sourceInfo.width}x${sourceInfo.height} / ${formatNumber(sourceInfo.fps)} fps / ${formatDuration(sourceInfo.duration)}`
          : '等待读取素材信息',
      ],
    },
    {
      title: '策略',
      lines: strategyLines,
    },
    {
      title: '运行时',
      lines: [
        snapshot.interpolation.tensorBackend,
        `RIFE ${snapshot.interpolation.model} / ${snapshot.workflow.fpsMode === 'target' ? `目标 ${snapshot.interpolation.targetFps} fps` : `${snapshot.interpolation.multi}x 倍率`}`,
        `Scale ${snapshot.interpolation.scale.toFixed(1)} / ${snapshot.interpolation.fp16 ? 'FP16' : 'FP32'}`,
      ],
    },
    {
      title: '编码',
      lines: [
        snapshot.encode.codec,
        `CRF ${snapshot.encode.crf}`,
        snapshot.encode.preset,
      ],
    },
    {
      title: '输出',
      lines: [
        snapshot.output.outputPath || '自动生成输出文件名',
        snapshot.output.outputDir || '默认输出目录',
        snapshot.output.tempDir || '默认缓存目录',
      ],
    },
  ]
}

export function formatDuration(durationSeconds: number): string {
  const safe = Number.isFinite(durationSeconds) ? Math.max(durationSeconds, 0) : 0
  const total = Math.round(safe)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60

  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
  }

  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
}

export function formatNumber(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.01) {
    return `${Math.round(value)}`
  }

  return value.toFixed(2).replace(/\.?0+$/, '')
}
