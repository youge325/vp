import type { ProcessOrder, StepDefinition, WorkflowMode } from '@/types'

export const WORKFLOW_LABELS: Record<WorkflowMode, string> = {
  frame_interpolation: '视频补帧',
  super_resolution: '超分辨率',
  anime_optimization: '动漫优化',
  format_conversion: '格式转换',
}

export const PROCESS_ORDER_LABELS: Record<ProcessOrder, string> = {
  super_resolution_then_interpolation: '先超分后补帧',
  frame_interpolation_then_super_resolution: '先补帧后超分',
}

export const WORKFLOW_STEPS: StepDefinition[] = [
  {
    key: 'overview',
    index: 1,
    title: '概览',
    path: '/',
    subtitle: '环境、资源与工作台总览',
  },
  {
    key: 'source',
    index: 2,
    title: '素材',
    path: '/source',
    subtitle: '导入视频并读取素材信息',
  },
  {
    key: 'interpolation',
    index: 3,
    title: '视频补帧',
    path: '/interpolation',
    subtitle: 'RIFE、倍速和目标帧率',
  },
  {
    key: 'super-resolution',
    index: 4,
    title: '超分辨率',
    path: '/super-resolution',
    subtitle: '超分步骤和联动顺序',
  },
  {
    key: 'anime',
    index: 5,
    title: '动漫优化',
    path: '/anime',
    subtitle: '针对二次元内容的预设区',
  },
  {
    key: 'format',
    index: 6,
    title: '格式转换',
    path: '/format',
    subtitle: '封装、转码和交付策略',
  },
  {
    key: 'deliver',
    index: 7,
    title: '输出与执行',
    path: '/deliver',
    subtitle: '编码、输出和任务执行',
  },
  {
    key: 'preview',
    index: 8,
    title: '结果预览',
    path: '/preview',
    subtitle: '输出结果、日志和定位',
  },
]

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

export const CODEC_OPTIONS = ['libx264', 'libx265', 'libvpx-vp9', 'libaom-av1', 'copy']
export const PRESET_OPTIONS = [
  'ultrafast',
  'superfast',
  'veryfast',
  'faster',
  'fast',
  'medium',
  'slow',
  'slower',
  'veryslow',
]

export const VIDEO_EXTENSIONS = ['mp4', 'avi', 'mkv', 'mov', 'flv', 'webm', 'wmv']
