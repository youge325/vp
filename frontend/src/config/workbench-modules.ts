export const WORKBENCH_MODULE_META = [
  { key: 'home', title: '主页', path: '/home' },
  { key: 'input', title: '输入', path: '/input' },
  { key: 'decode', title: '解码', path: '/decode' },
  { key: 'preprocess', title: '预处理', path: '/preprocess' },
  { key: 'enhance', title: '增强', path: '/enhance' },
  { key: 'postprocess', title: '后处理', path: '/postprocess' },
  { key: 'encode', title: '编码', path: '/encode' },
  { key: 'render', title: '渲染', path: '/render' },
] as const

export type ModuleKey = (typeof WORKBENCH_MODULE_META)[number]['key']

export const DEFAULT_WORKBENCH_MODULE_KEY: ModuleKey = WORKBENCH_MODULE_META[0].key
