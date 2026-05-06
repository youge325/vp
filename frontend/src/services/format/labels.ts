// pure: no Vue / no Pinia / no Tauri
// UI 标签格式化 — 按业务规则把领域数据投影成显示字符串。

import type { MediaItem } from '@/types/domain/media'
import type { BatchState } from '@/types/domain/batch'
import type { EncoderProfileSpec } from '@/types/domain/capability'
import { WORKFLOW_LABELS } from '@/services/workflow/modules'
import { resolvePrimaryMode } from '@/services/preset/profile-picker'

export type WorkflowStage = 'decode' | 'preprocess' | 'enhance' | 'postprocess' | 'encode'

const STAGE_PRESET_CAPTIONS: Record<WorkflowStage, string> = {
  decode: '启动探测完成后即可直接设置解码策略,后续新导入的视频会继承这些默认值。',
  preprocess: '预处理滤镜链会在解码之后、增强之前执行,可用来缩放帧尺寸等。',
  enhance: '增强参数可以在导入前先配置好,新导入的视频会直接继承这些默认设置。',
  postprocess: '后处理滤镜链会在增强之后、编码之前执行,可用来锐化、降噪或缩放到目标分辨率。',
  encode: '编码与输出参数会保存为默认预设,后续导入的新文件会直接继承这些设置。',
}

const STAGE_NON_PRESET_CAPTIONS: Record<WorkflowStage, string> = {
  decode: '当前修改会同步到激活文件与所有已勾选文件,解码器参数来自 FFmpeg 能力探测。',
  preprocess: '当前修改会同步到激活文件与所有已勾选文件。',
  enhance: '当前修改会同步到激活文件与所有已勾选文件,方便批量套用增强流程。',
  postprocess: '当前修改会同步到激活文件与所有已勾选文件。',
  encode: '当前修改会同步到激活文件与所有已勾选文件,适合批量统一编码策略。',
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
  stage: WorkflowStage = 'enhance',
): { targetLabel: string; caption: string } {
  if (isPresetMode) {
    return {
      targetLabel: '默认预设(后续导入会继承)',
      caption: STAGE_PRESET_CAPTIONS[stage],
    }
  }
  return {
    targetLabel: `作用于 ${selectionCount} 个文件`,
    caption: STAGE_NON_PRESET_CAPTIONS[stage],
  }
}

export function getProbeSourceLabel(source: string | null): string {
  if (source === 'cache') return '缓存'
  if (source === 'probe') return '实时探测'
  return '--'
}

export const BACKEND_LABELS: Record<string, string> = {
  pytorch: 'PyTorch',
  paddle: 'PaddlePaddle',
  onnx: 'ONNX Runtime',
}

export const ENGINE_LABELS: Record<string, string> = {
  cuda: 'CUDA',
  tensorrt: 'TensorRT',
  dcu: 'DCU',
  directml: 'DirectML',
  rocm: 'ROCm',
  cpu: 'CPU',
}
