// pure: no Vue / no Pinia / no Tauri
// Workbench 模块常量、流程标签、RIFE 模型枚举、容器/码控选项。
// 注意: WORKBENCH_MODULES 含 Vue Component 字段,移到 src/views/registry.ts。

import type { ProcessOrder, RateControlMode } from '@/types/domain/workflow'
import type { WorkflowMode } from '@/types/domain/workflow'

export const WORKFLOW_LABELS: Record<WorkflowMode, string> = {
  frame_interpolation: '补帧',
  super_resolution: '超分',
  anime_optimization: '动漫优化',
  format_conversion: '转码',
}

export const PROCESS_ORDER_LABELS: Record<ProcessOrder, string> = {
  super_resolution_then_interpolation: '先超分后补帧',
  frame_interpolation_then_super_resolution: '先补帧后超分',
}

export const RATE_CONTROL_LABELS: Record<RateControlMode, string> = {
  crf: 'CRF',
  cq: 'CQ',
  qp: 'QP',
  bitrate: 'Bitrate',
}

export const RIFE_MODELS = [
  '4.0',
  '4.1',
  '4.2',
  '4.3',
  '4.4',
  '4.5',
  '4.6',
  '4.7',
  '4.8',
  '4.9',
  '4.10',
  '4.11',
  '4.12',
  '4.12.lite',
  '4.13',
  '4.13.lite',
  '4.14',
  '4.14.lite',
  '4.15',
  '4.15.lite',
  '4.16.lite',
  '4.17',
  '4.17.lite',
  '4.18',
  '4.19',
  '4.20',
  '4.21',
  '4.22',
  '4.22.lite',
  '4.23',
  '4.24',
  '4.25',
  '4.25.lite',
  '4.25.heavy',
  '4.26',
  '4.26.heavy',
]

export const VIDEO_EXTENSIONS = ['mp4', 'avi', 'mkv', 'mov', 'flv', 'webm', 'wmv', 'ts']

export const CONTAINER_OPTIONS = ['mp4', 'mkv', 'mov']
