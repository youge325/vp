// pure: no Vue / no Pinia / no Tauri
// UI 标签格式化 — 按业务规则把领域数据投影成显示字符串。

import type { BatchState } from '@/types/domain/batch'
import type { CodecProfileSpec, WorkflowConfig } from '@/types/protocol'

const FORMAT_CONVERSION_LABEL = '转码'

export function getWorkflowSummaryLabel(workflowConfig: WorkflowConfig): string {
  const labels = [
    workflowConfig.interpolation.enabled ? '补帧' : null,
    workflowConfig.superResolution.enabled ? '超分' : null,
  ].filter(Boolean)

  return labels.length > 0
    ? labels.join(' / ')
    : FORMAT_CONVERSION_LABEL
}

export function groupEncoderProfilesByFamily(
  profiles: CodecProfileSpec[],
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
): string {
  if (isPresetMode) {
    return '默认预设'
  }
  return `作用于 ${selectionCount} 个文件`
}

export function getProbeSourceLabel(source: string | null): string {
  if (source === 'cache') return '缓存'
  if (source === 'probe') return '实时探测'
  return '--'
}
