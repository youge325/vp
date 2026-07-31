import { animeCleanupParamsForProfile } from './anime-cleanup'
import type { FilterStep, FilterStepKind } from '@/types/protocol'

type FilterStepFor<Kind extends FilterStepKind> = Extract<FilterStep, { kind: Kind }>
type FilterParamKey<Kind extends FilterStepKind> = Kind extends FilterStepKind
  ? keyof FilterStepFor<Kind>['params'] & string
  : never

export interface FilterFieldDefinition<Kind extends FilterStepKind = FilterStepKind> {
  key: FilterParamKey<Kind>
  label: string
  type: 'number' | 'text'
  min?: number
  max?: number
  step?: number
}

interface FilterEditorDefinition<Kind extends FilterStepKind> {
  columns: 2 | 3 | 4
  fields: readonly FilterFieldDefinition<Kind>[]
}

export interface FilterCatalogEntry<Kind extends FilterStepKind = FilterStepKind> {
  kind: Kind
  label: string
  defaultStep: Readonly<FilterStepFor<Kind>>
  editor?: FilterEditorDefinition<Kind>
}

interface FilterCatalogDefinition<Kind extends FilterStepKind> extends FilterCatalogEntry<Kind> {
  defaultStep: FilterStepFor<Kind>
}

type FilterCatalogByKind = {
  [Kind in FilterStepKind]: FilterCatalogDefinition<Kind>
}

const CATALOG_BY_KIND: FilterCatalogByKind = {
  scale: {
    kind: 'scale',
    label: '缩放',
    defaultStep: {
      kind: 'scale',
      enabled: true,
      params: { mode: 'factor', factor: 0.5, width: 1920, height: 1080, interpolation: 'lanczos4' },
    },
  },
  crop: {
    kind: 'crop',
    label: '裁剪',
    defaultStep: { kind: 'crop', enabled: true, params: { x: 0, y: 0, width: 1920, height: 1080 } },
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
  pad: {
    kind: 'pad',
    label: '填充',
    defaultStep: {
      kind: 'pad',
      enabled: true,
      params: { top: 0, bottom: 0, left: 0, right: 0, color: '#000000' },
    },
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
  sharpen: {
    kind: 'sharpen',
    label: '锐化',
    defaultStep: { kind: 'sharpen', enabled: true, params: { amount: 0.5 } },
    editor: {
      columns: 2,
      fields: [{ key: 'amount', label: '强度 (0~1)', type: 'number', min: 0, max: 1, step: 0.05 }],
    },
  },
  denoise: {
    kind: 'denoise',
    label: '降噪',
    defaultStep: { kind: 'denoise', enabled: true, params: { strength: 10, colorStrength: 10 } },
    editor: {
      columns: 2,
      fields: [
        { key: 'strength', label: '强度 (1~20)', type: 'number', min: 1, max: 20 },
        { key: 'colorStrength', label: '色彩强度 (1~20)', type: 'number', min: 1, max: 20 },
      ],
    },
  },
  color: {
    kind: 'color',
    label: '色彩调整',
    defaultStep: { kind: 'color', enabled: true, params: { brightness: 0, contrast: 1, saturation: 1 } },
    editor: {
      columns: 3,
      fields: [
        { key: 'brightness', label: '亮度 (-1~1)', type: 'number', min: -1, max: 1, step: 0.05 },
        { key: 'contrast', label: '对比度 (0~3)', type: 'number', min: 0, max: 3, step: 0.05 },
        { key: 'saturation', label: '饱和度 (0~3)', type: 'number', min: 0, max: 3, step: 0.05 },
      ],
    },
  },
  anime_cleanup: {
    kind: 'anime_cleanup',
    label: 'Anime 清理',
    defaultStep: {
      kind: 'anime_cleanup',
      enabled: true,
      params: animeCleanupParamsForProfile('clean-lines'),
    },
  },
}

export const FILTER_CATALOG: readonly FilterCatalogEntry[] = Object.values(CATALOG_BY_KIND)

export function getFilterCatalogEntry<Kind extends FilterStepKind>(kind: Kind): FilterCatalogEntry<Kind> {
  return CATALOG_BY_KIND[kind]
}

export function createDefaultFilterStep<Kind extends FilterStepKind>(kind: Kind): FilterStepFor<Kind> {
  return structuredClone(CATALOG_BY_KIND[kind].defaultStep)
}
