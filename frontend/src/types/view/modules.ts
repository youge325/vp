// 视图层 — Workbench 模块定义(含 Vue Component 字段,唯一允许 import vue 的 types 模块)。

import type { Component } from 'vue'

export type ModuleKey = 'home' | 'input' | 'decode' | 'preprocess' | 'enhance' | 'postprocess' | 'encode' | 'render'

export interface WorkbenchModuleDefinition {
  key: ModuleKey
  title: string
  path: string
  icon: Component
}
