// pure: no Vue / no Pinia / no Tauri
// UI 标签格式化 — 按业务规则把领域数据投影成显示字符串。

import type { MediaItem } from '@/types/domain/media'
import type { BatchState } from '@/types/domain/batch'
import type { EncoderProfileSpec } from '@/types/domain/capability'
import type { WorkflowMode } from '@/types/domain/workflow'

const WORKFLOW_LABELS: Record<WorkflowMode, string> = {
  frame_interpolation: '补帧',
  super_resolution: '超分',
  anime_optimization: '动漫优化',
  format_conversion: '转码',
}

export function resolvePrimaryMode(item: Pick<MediaItem, 'workflowConfig'>): WorkflowMode {
  const wf = item.workflowConfig
  if (wf.interpolation.enabled) return 'frame_interpolation'
  if (wf.superResolution.enabled) return 'super_resolution'
  if (wf.anime.enabled) return 'anime_optimization'
  return 'format_conversion'
}

export function getWorkflowSummaryLabel(item: MediaItem): string {
  const labels = [
    item.workflowConfig.interpolation.enabled ? '补帧' : null,
    item.workflowConfig.superResolution.enabled ? '超分' : null,
    item.workflowConfig.anime.enabled ? '动漫' : null,
  ].filter(Boolean)

  return labels.length > 0
    ? labels.join(' / ')
    : WORKFLOW_LABELS[resolvePrimaryMode(item)]
}

export function groupEncoderProfilesByFamily(
  profiles: EncoderProfileSpec[],
): Array<{ title: string; value: string }> {
  return [
    {
      title: 'CPU',
      value: profiles
        .filter((p) => p.family === 'cpu')
        .map((p) => p.name)
        .join(', ') || '--',
    },
    {
      title: 'NVENC',
      value: profiles
        .filter((p) => p.family === 'nvidia')
        .map((p) => p.name)
        .join(', ') || '--',
    },
    {
      title: 'QSV',
      value: profiles
        .filter((p) => p.family === 'intel')
        .map((p) => p.name)
        .join(', ') || '--',
    },
  ]
}

export function getTaskStatusLabel(batch: BatchState, currentItemStatus: string | null): string {
  if (batch.isRunning) {
    return currentItemStatus ?? 'running'
  }
  return 'idle'
}

export function getEditingScopeLabel(
  isPresetMode: boolean,
  selectionCount: number,
): { targetLabel: string } {
  if (isPresetMode) {
    return {
      targetLabel: '默认预设',
    }
  }
  return {
    targetLabel: `作用于 ${selectionCount} 个文件`,
  }
}

export function getProbeSourceLabel(source: string | null): string {
  if (source === 'cache') return '缓存'
  if (source === 'probe') return '实时探测'
  return '--'
}
