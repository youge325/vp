import { animeCleanupParamsForProfile } from './anime-cleanup'
import type { FilterStep, FilterStepKind } from '@/types/protocol'

interface FilterCatalogEntry {
  kind: FilterStepKind
  label: string
  defaultParams: Readonly<FilterStep['params']>
}

export const FILTER_CATALOG: readonly FilterCatalogEntry[] = [
  {
    kind: 'scale',
    label: '缩放',
    defaultParams: { mode: 'factor', factor: 0.5, width: 1920, height: 1080, interpolation: 'lanczos4' },
  },
  { kind: 'crop', label: '裁剪', defaultParams: { x: 0, y: 0, width: 1920, height: 1080 } },
  { kind: 'pad', label: '填充', defaultParams: { top: 0, bottom: 0, left: 0, right: 0, color: '#000000' } },
  { kind: 'sharpen', label: '锐化', defaultParams: { amount: 0.5 } },
  { kind: 'denoise', label: '降噪', defaultParams: { strength: 10, colorStrength: 10 } },
  { kind: 'color', label: '色彩调整', defaultParams: { brightness: 0, contrast: 1, saturation: 1 } },
  { kind: 'anime_cleanup', label: 'Anime 清理', defaultParams: animeCleanupParamsForProfile('clean-lines') },
] as const

const CATALOG_BY_KIND = new Map(FILTER_CATALOG.map((entry) => [entry.kind, entry]))

export function createDefaultFilterStep(kind: FilterStepKind): FilterStep {
  const entry = CATALOG_BY_KIND.get(kind)
  if (!entry) throw new Error(`Unknown filter kind: ${kind}`)
  return { kind, enabled: true, params: { ...entry.defaultParams } }
}

export function filterLabel(kind: FilterStepKind): string {
  return CATALOG_BY_KIND.get(kind)?.label ?? kind
}
