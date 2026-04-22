import type {
  ProcessOrder,
  StageDefinition,
  StageTabDefinition,
  StepDefinition,
  WorkflowMode,
} from '@/types'

export const WORKFLOW_LABELS: Record<WorkflowMode, string> = {
  frame_interpolation: '补帧',
  super_resolution: '超分',
  anime_optimization: '动漫',
  format_conversion: '转码',
}

export const PROCESS_ORDER_LABELS: Record<ProcessOrder, string> = {
  super_resolution_then_interpolation: '先超分后补帧',
  frame_interpolation_then_super_resolution: '先补帧后超分',
}

export const WORKBENCH_STAGES: StageDefinition[] = [
  { key: 'prepare', index: 1, title: '准备', path: '/prepare' },
  { key: 'enhance', index: 2, title: '增强', path: '/enhance' },
  { key: 'deliver', index: 3, title: '交付', path: '/deliver' },
  { key: 'results', index: 4, title: '结果', path: '/results' },
]

export const PREPARE_TABS: StageTabDefinition[] = [
  { key: 'environment', label: '环境' },
  { key: 'input', label: '输入' },
]

export const WORKFLOW_STEPS: StepDefinition[] = [
  {
    key: 'overview',
    index: 1,
    title: '环境',
    path: '/',
    subtitle: '环境检查',
    stage: 'prepare',
    tab: 'environment',
  },
  {
    key: 'source',
    index: 2,
    title: '输入',
    path: '/source',
    subtitle: '输入路径',
    stage: 'prepare',
    tab: 'input',
  },
  {
    key: 'interpolation',
    index: 3,
    title: '补帧',
    path: '/interpolation',
    subtitle: '补帧参数',
    stage: 'enhance',
    tab: 'enhance',
  },
  {
    key: 'super-resolution',
    index: 4,
    title: '超分',
    path: '/super-resolution',
    subtitle: '超分参数',
    stage: 'enhance',
    tab: 'enhance',
  },
  {
    key: 'anime',
    index: 5,
    title: '动漫',
    path: '/anime',
    subtitle: '动漫参数',
    stage: 'enhance',
    tab: 'enhance',
  },
  {
    key: 'format',
    index: 6,
    title: '编解码',
    path: '/format',
    subtitle: '编码设置',
    stage: 'deliver',
    tab: 'deliver',
  },
  {
    key: 'deliver',
    index: 7,
    title: '运行',
    path: '/deliver',
    subtitle: '启动流程',
    stage: 'deliver',
    tab: 'deliver',
  },
  {
    key: 'preview',
    index: 8,
    title: '日志',
    path: '/preview',
    subtitle: 'CLI 输出',
    stage: 'results',
    tab: 'results',
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
