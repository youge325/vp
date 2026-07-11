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
  WORKBENCH_MODULE_META,
  type ModuleKey,
} from '@/config/workbench-modules'
import type { WorkbenchModuleDefinition } from '@/types/view/modules'

const ICON_MAP: Record<ModuleKey, typeof BookOutline> = {
  home:        BookOutline,
  input:       AddCircleOutline,
  decode:      HardwareChipOutline,
  preprocess:  OptionsOutline,
  enhance:     ConstructOutline,
  postprocess: ColorWandOutline,
  encode:      ColorFillOutline,
  render:      SendOutline,
}

export const WORKBENCH_MODULES: WorkbenchModuleDefinition[] = WORKBENCH_MODULE_META.map((meta) => ({
  ...meta,
  icon: ICON_MAP[meta.key],
}))

export const WORKBENCH_MODULE_BY_KEY = Object.fromEntries(
  WORKBENCH_MODULES.map((module) => [module.key, module]),
) as Record<ModuleKey, WorkbenchModuleDefinition>
