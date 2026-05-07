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
  { title: string; path: string; description: string }
> = {
  home:        { title: '主页',   path: '/home',        description: '启动探测与能力概览' },
  input:       { title: '输入',   path: '/input',       description: '批量导入与素材管理' },
  decode:      { title: '解码',   path: '/decode',      description: '解码方案与硬件解码' },
  preprocess:  { title: '预处理', path: '/preprocess',  description: '解码后帧级图像处理' },
  enhance:     { title: '增强',   path: '/enhance',     description: '补帧 / 超分 / 动漫' },
  postprocess: { title: '后处理', path: '/postprocess', description: '增强后帧级图像处理' },
  encode:      { title: '编码',   path: '/encode',      description: '编码器与输出目录' },
  render:      { title: '渲染',   path: '/render',      description: '批量队列执行' },
}
