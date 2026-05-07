import type { ModuleKey } from '@/types/view/modules'

export const WORKBENCH_MODULE_KEYS: ModuleKey[] = [
  'home',
  'input',
  'decode',
  'preprocess',
  'enhance',
  'postprocess',
  'encode',
  'render',
]

export const WORKBENCH_MODULE_META: Record<
  ModuleKey,
  { title: string; path: string }
> = {
  home:        { title: '主页',   path: '/home' },
  input:       { title: '输入',   path: '/input' },
  decode:      { title: '解码',   path: '/decode' },
  preprocess:  { title: '预处理', path: '/preprocess' },
  enhance:     { title: '增强',   path: '/enhance' },
  postprocess: { title: '后处理', path: '/postprocess' },
  encode:      { title: '编码',   path: '/encode' },
  render:      { title: '渲染',   path: '/render' },
}
