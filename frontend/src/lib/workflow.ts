import {
  AddCircleOutline,
  BookOutline,
  ColorFillOutline,
  ConstructOutline,
  GlassesOutline,
  SendOutline,
} from '@vicons/ionicons5'
import type { ProcessOrder, WorkbenchModuleDefinition, WorkflowMode } from '@/types'

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

export const WORKBENCH_MODULES: WorkbenchModuleDefinition[] = [
  {
    key: 'home',
    title: '主页',
    path: '/home',
    description: '环境与概览',
    icon: BookOutline,
  },
  {
    key: 'input',
    title: '输入',
    path: '/input',
    description: '素材导入',
    icon: AddCircleOutline,
  },
  {
    key: 'enhance',
    title: '增强',
    path: '/enhance',
    description: '补帧 / 超分 / 动漫',
    icon: ConstructOutline,
  },
  {
    key: 'encode',
    title: '编码',
    path: '/encode',
    description: '输出与编码',
    icon: ColorFillOutline,
  },
  {
    key: 'render',
    title: '渲染',
    path: '/render',
    description: '任务控制',
    icon: SendOutline,
  },
  {
    key: 'preview',
    title: '预览',
    path: '/preview',
    description: '日志与输出',
    icon: GlassesOutline,
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
