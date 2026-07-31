import { describe, expect, it } from 'vitest'

import { FILTER_CATALOG, createDefaultFilterStep, getFilterCatalogEntry } from '@/services/filters/filter-catalog'

describe('filter catalog', () => {
  it('contains Anime cleanup as a real filter kind', () => {
    expect(FILTER_CATALOG.map((entry) => entry.kind)).toEqual([
      'scale',
      'crop',
      'pad',
      'sharpen',
      'denoise',
      'color',
      'anime_cleanup',
    ])
    expect(getFilterCatalogEntry('anime_cleanup').label).toBe('Anime 清理')
  })

  it('describes simple filter fields without duplicating defaults', () => {
    const pad = getFilterCatalogEntry('pad')

    expect(pad.editor?.columns).toBe(3)
    expect(pad.editor?.fields.map(({ key }) => key)).toEqual(['top', 'bottom', 'left', 'right', 'color'])
    expect(pad.editor?.fields.slice(0, 4).every(({ min, type }) => min === 0 && type === 'number')).toBe(true)
    expect(pad.editor?.fields.at(-1)?.type).toBe('text')
    expect(pad.defaultStep.params).toEqual({ top: 0, bottom: 0, left: 0, right: 0, color: '#000000' })
  })

  it('creates independent default params', () => {
    const first = createDefaultFilterStep('anime_cleanup')
    const second = createDefaultFilterStep('anime_cleanup')

    first.params.denoise = 99
    expect(second).toEqual({
      kind: 'anime_cleanup',
      enabled: true,
      params: { profile: 'clean-lines', denoise: 15, edgeBoost: 30 },
    })
  })
})
