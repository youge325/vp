import { describe, expect, it } from 'vitest'

import { FILTER_CATALOG, createDefaultFilterStep, filterLabel } from '@/services/filters/filter-catalog'

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
    expect(filterLabel('anime_cleanup')).toBe('Anime 清理')
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
