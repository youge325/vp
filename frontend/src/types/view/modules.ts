// 视图层 — Workbench 模块定义(含 Vue Component 字段,唯一允许 import vue 的 types 模块)。

import type { Component } from 'vue'
import type { ModuleKey } from '@/config/workbench-modules'

export interface WorkbenchModuleDefinition {
  key: ModuleKey
  title: string
  path: string
  icon: Component
}
