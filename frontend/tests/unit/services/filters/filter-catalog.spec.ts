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

    expect(pad.editor).toEqual({
      columns: 3,
      fields: [
        { key: 'top', label: '上', type: 'number', min: 0 },
        { key: 'bottom', label: '下', type: 'number', min: 0 },
        { key: 'left', label: '左', type: 'number', min: 0 },
        { key: 'right', label: '右', type: 'number', min: 0 },
        { key: 'color', label: '颜色 (hex)', type: 'text' },
      ],
    })
    expect(pad.defaultParams).toEqual({ top: 0, bottom: 0, left: 0, right: 0, color: '#000000' })
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
