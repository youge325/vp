// 视图层注册表 — Workbench 模块到 Vue 组件的映射。
// types/view/modules.ts 定义结构,这里实例化(因为含 Component 字段)。

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
import type { WorkbenchModuleDefinition } from '@/types/view/modules'

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
