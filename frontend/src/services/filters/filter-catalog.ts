import { animeCleanupParamsForProfile } from './anime-cleanup'
import type { FilterStep, FilterStepKind } from '@/types/protocol'

export interface FilterFieldDefinition {
  key: string
  label: string
  type: 'number' | 'text'
  min?: number
  max?: number
  step?: number
}

interface FilterEditorDefinition {
  columns: 2 | 3 | 4
  fields: readonly FilterFieldDefinition[]
}

export interface FilterCatalogEntry {
  kind: FilterStepKind
  label: string
  defaultParams: Readonly<FilterStep['params']>
  editor?: FilterEditorDefinition
}

export const FILTER_CATALOG: readonly FilterCatalogEntry[] = [
  {
    kind: 'scale',
    label: '缩放',
    defaultParams: { mode: 'factor', factor: 0.5, width: 1920, height: 1080, interpolation: 'lanczos4' },
  },
  {
    kind: 'crop',
    label: '裁剪',
    defaultParams: { x: 0, y: 0, width: 1920, height: 1080 },
    editor: {
      columns: 4,
      fields: [
        { key: 'x', label: 'X', type: 'number', min: 0 },
        { key: 'y', label: 'Y', type: 'number', min: 0 },
        { key: 'width', label: '宽度', type: 'number', min: 1 },
        { key: 'height', label: '高度', type: 'number', min: 1 },
      ],
    },
  },
  {
    kind: 'pad',
    label: '填充',
    defaultParams: { top: 0, bottom: 0, left: 0, right: 0, color: '#000000' },
    editor: {
      columns: 3,
      fields: [
        { key: 'top', label: '上', type: 'number', min: 0 },
        { key: 'bottom', label: '下', type: 'number', min: 0 },
        { key: 'left', label: '左', type: 'number', min: 0 },
        { key: 'right', label: '右', type: 'number', min: 0 },
        { key: 'color', label: '颜色 (hex)', type: 'text' },
      ],
    },
  },
  {
    kind: 'sharpen',
    label: '锐化',
    defaultParams: { amount: 0.5 },
    editor: {
      columns: 2,
      fields: [{ key: 'amount', label: '强度 (0~1)', type: 'number', min: 0, max: 1, step: 0.05 }],
    },
  },
  {
    kind: 'denoise',
    label: '降噪',
    defaultParams: { strength: 10, colorStrength: 10 },
    editor: {
      columns: 2,
      fields: [
        { key: 'strength', label: '强度 (1~20)', type: 'number', min: 1, max: 20 },
        { key: 'colorStrength', label: '色彩强度 (1~20)', type: 'number', min: 1, max: 20 },
      ],
    },
  },
  {
    kind: 'color',
    label: '色彩调整',
    defaultParams: { brightness: 0, contrast: 1, saturation: 1 },
    editor: {
      columns: 3,
      fields: [
        { key: 'brightness', label: '亮度 (-1~1)', type: 'number', min: -1, max: 1, step: 0.05 },
        { key: 'contrast', label: '对比度 (0~3)', type: 'number', min: 0, max: 3, step: 0.05 },
        { key: 'saturation', label: '饱和度 (0~3)', type: 'number', min: 0, max: 3, step: 0.05 },
      ],
    },
  },
  { kind: 'anime_cleanup', label: 'Anime 清理', defaultParams: animeCleanupParamsForProfile('clean-lines') },
] as const

const CATALOG_BY_KIND = new Map(FILTER_CATALOG.map((entry) => [entry.kind, entry]))

export function getFilterCatalogEntry(kind: FilterStepKind): FilterCatalogEntry {
  const entry = CATALOG_BY_KIND.get(kind)
  if (!entry) throw new Error(`Unknown filter kind: ${kind}`)
  return entry
}

export function createDefaultFilterStep(kind: FilterStepKind): FilterStep {
  const entry = getFilterCatalogEntry(kind)
  return { kind, enabled: true, params: { ...entry.defaultParams } }
}
