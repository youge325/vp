import { animeCleanupParamsForProfile } from './anime-cleanup'
import { APPLICATION_DEFAULTS, FILTER_FIELD_CONSTRAINTS } from '@/types/protocol'
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
  pattern?: string
}

interface FilterFieldConstraint {
  readonly minimum?: number
  readonly exclusiveMinimum?: number
  readonly maximum?: number
  readonly enum?: readonly string[]
  readonly pattern?: string
}

const FILTER_CONSTRAINTS: Readonly<Record<FilterStepKind, Readonly<Record<string, FilterFieldConstraint>>>>
  = FILTER_FIELD_CONSTRAINTS

function field<Kind extends FilterStepKind>(
  kind: Kind,
  key: FilterParamKey<Kind>,
  label: string,
  type: 'number' | 'text',
  step?: number,
): FilterFieldDefinition<Kind> {
  const constraint = FILTER_CONSTRAINTS[kind][key]
  return {
    key,
    label,
    type,
    ...(constraint?.minimum === undefined ? {} : { min: constraint.minimum }),
    ...(constraint?.maximum === undefined ? {} : { max: constraint.maximum }),
    ...(constraint?.pattern === undefined ? {} : { pattern: constraint.pattern }),
    ...(step === undefined ? {} : { step }),
  }
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
      params: { ...APPLICATION_DEFAULTS.filters.scale },
    },
  },
  crop: {
    kind: 'crop',
    label: '裁剪',
    defaultStep: { kind: 'crop', enabled: true, params: { ...APPLICATION_DEFAULTS.filters.crop } },
    editor: {
      columns: 4,
      fields: [
        field('crop', 'x', 'X', 'number'),
        field('crop', 'y', 'Y', 'number'),
        field('crop', 'width', '宽度', 'number'),
        field('crop', 'height', '高度', 'number'),
      ],
    },
  },
  pad: {
    kind: 'pad',
    label: '填充',
    defaultStep: {
      kind: 'pad',
      enabled: true,
      params: { ...APPLICATION_DEFAULTS.filters.pad },
    },
    editor: {
      columns: 3,
      fields: [
        field('pad', 'top', '上', 'number'),
        field('pad', 'bottom', '下', 'number'),
        field('pad', 'left', '左', 'number'),
        field('pad', 'right', '右', 'number'),
        field('pad', 'color', '颜色 (hex)', 'text'),
      ],
    },
  },
  sharpen: {
    kind: 'sharpen',
    label: '锐化',
    defaultStep: { kind: 'sharpen', enabled: true, params: { ...APPLICATION_DEFAULTS.filters.sharpen } },
    editor: {
      columns: 2,
      fields: [field('sharpen', 'amount', '强度 (0~1)', 'number', 0.05)],
    },
  },
  denoise: {
    kind: 'denoise',
    label: '降噪',
    defaultStep: { kind: 'denoise', enabled: true, params: { ...APPLICATION_DEFAULTS.filters.denoise } },
    editor: {
      columns: 2,
      fields: [
        field('denoise', 'strength', '强度 (0~20)', 'number'),
        field('denoise', 'colorStrength', '色彩强度 (0~20)', 'number'),
      ],
    },
  },
  color: {
    kind: 'color',
    label: '色彩调整',
    defaultStep: { kind: 'color', enabled: true, params: { ...APPLICATION_DEFAULTS.filters.color } },
    editor: {
      columns: 3,
      fields: [
        field('color', 'brightness', '亮度 (-1~1)', 'number', 0.05),
        field('color', 'contrast', '对比度 (0~3)', 'number', 0.05),
        field('color', 'saturation', '饱和度 (0~3)', 'number', 0.05),
      ],
    },
  },
  anime_cleanup: {
    kind: 'anime_cleanup',
    label: 'Anime 清理',
    defaultStep: {
      kind: 'anime_cleanup',
      enabled: true,
      params: animeCleanupParamsForProfile(APPLICATION_DEFAULTS.filters.animeCleanup.defaultProfile),
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
