// 视图层注册表 — Workbench 模块到 Vue 组件的映射。
// 纯数据定义在 config/workbench-modules;这里附加 icon 组件(视图层资产)。

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
import {
  WORKBENCH_MODULE_KEYS,
  WORKBENCH_MODULE_META,
} from '@/config/workbench-modules'
import type { WorkbenchModuleDefinition } from '@/types/view/modules'

const ICON_MAP: Record<string, typeof BookOutline> = {
  home:        BookOutline,
  input:       AddCircleOutline,
  decode:      HardwareChipOutline,
  preprocess:  OptionsOutline,
  enhance:     ConstructOutline,
  postprocess: ColorWandOutline,
  encode:      ColorFillOutline,
  render:      SendOutline,
}

export const WORKBENCH_MODULES: WorkbenchModuleDefinition[] = WORKBENCH_MODULE_KEYS.map((key) => {
  const meta = WORKBENCH_MODULE_META[key]
  return {
    key,
    title: meta.title,
    path: meta.path,
    description: meta.description,
    icon: ICON_MAP[key],
  }
})
