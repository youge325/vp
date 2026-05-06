/** 格式化与显示辅助纯函数。
 *
 * 不引用任何 Store，只接收原始数据并返回 UI 显示字符串。
 */


import type { MediaItem, BatchState, EncoderProfileSpec } from '@/types'
import { WORKFLOW_LABELS } from '@/lib/workflow'
import { resolvePrimaryMode } from '@/lib/task-mapper'

/**
 * 根据 workflow 配置生成流程摘要标签（如 "补帧 / 超分"）。
 */
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

/**
 * 将编码器配置按家族分组，用于 Home 页面展示。
 */
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

/**
 * 根据 batch 运行状态返回全局任务状态标签。
 */
export function getTaskStatusLabel(batch: BatchState, currentItemStatus: string | null): string {
  if (batch.isRunning) {
    return currentItemStatus ?? 'running'
  }
  return 'idle'
}

/**
 * 返回编辑范围标签（用于 Enhance/Decode/Encode 页面头部）。
 */
export function getEditingScopeLabel(
  isPresetMode: boolean,
  selectionCount: number,
): { targetLabel: string; caption: string } {
  if (isPresetMode) {
    return {
      targetLabel: '默认预设（后续导入会继承）',
      caption: '增强参数可以在导入前先配置好，新导入的视频会直接继承这些默认设置。',
    }
  }
  return {
    targetLabel: `作用于 ${selectionCount} 个文件`,
    caption: '当前修改会同步到激活文件与所有已勾选文件，方便批量套用增强流程。',
  }
}

/**
 * 探测来源标签。
 */
export function getProbeSourceLabel(source: string | null): string {
  if (source === 'cache') return '缓存'
  if (source === 'probe') return '实时探测'
  return '--'
}

/**
 * 后端显示名称映射。
 */
export const BACKEND_LABELS: Record<string, string> = {
  pytorch: 'PyTorch',
  paddle: 'PaddlePaddle',
  onnx: 'ONNX Runtime',
}

/**
 * 引擎显示名称映射。
 */
export const ENGINE_LABELS: Record<string, string> = {
  cuda: 'CUDA',
  tensorrt: 'TensorRT',
  dcu: 'DCU',
  directml: 'DirectML',
  rocm: 'ROCm',
  cpu: 'CPU',
}
