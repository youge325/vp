import {
  AddCircleOutline,
  BookOutline,
  ColorFillOutline,
  ColorWandOutline,
  ConstructOutline,
  HardwareChipOutline,
  OptionsOutline,
  SendOutline,
} from '@vicons/ionicons5'
import type { ProcessOrder, RateControlMode, WorkbenchModuleDefinition, WorkflowMode } from '@/types'

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

export const WORKBENCH_MODULES: WorkbenchModuleDefinition[] = [
  {
    key: 'home',
    title: '主页',
    path: '/home',
    description: '启动探测与能力概览',
    icon: BookOutline,
  },
  {
    key: 'input',
    title: '输入',
    path: '/input',
    description: '批量导入与素材管理',
    icon: AddCircleOutline,
  },
  {
    key: 'decode',
    title: '解码',
    path: '/decode',
    description: '解码方案与硬件解码',
    icon: HardwareChipOutline,
  },
  {
    key: 'preprocess',
    title: '预处理',
    path: '/preprocess',
    description: '解码后帧级图像处理',
    icon: OptionsOutline,
  },
  {
    key: 'enhance',
    title: '增强',
    path: '/enhance',
    description: '补帧 / 超分 / 动漫',
    icon: ConstructOutline,
  },
  {
    key: 'postprocess',
    title: '后处理',
    path: '/postprocess',
    description: '增强后帧级图像处理',
    icon: ColorWandOutline,
  },
  {
    key: 'encode',
    title: '编码',
    path: '/encode',
    description: '编码器与输出目录',
    icon: ColorFillOutline,
  },
  {
    key: 'render',
    title: '渲染',
    path: '/render',
    description: '批量队列执行',
    icon: SendOutline,
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

export const VIDEO_EXTENSIONS = ['mp4', 'avi', 'mkv', 'mov', 'flv', 'webm', 'wmv', 'ts']

export const CONTAINER_OPTIONS = ['mp4', 'mkv', 'mov']

export const RATE_CONTROL_LABELS: Record<RateControlMode, string> = {
  crf: 'CRF',
  cq: 'CQ',
  qp: 'QP',
  bitrate: 'Bitrate',
}
