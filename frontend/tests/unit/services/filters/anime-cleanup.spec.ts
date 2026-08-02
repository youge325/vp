import { describe, expect, it } from 'vitest'

import {
  ANIME_CLEANUP_FIELD_CONSTRAINTS,
  ANIME_CLEANUP_PROFILE_OPTIONS,
  animeCleanupParamsForProfile,
} from '@/services/filters/anime-cleanup'

describe('anime cleanup profiles', () => {
  it('exposes the three stable profile choices', () => {
    expect(ANIME_CLEANUP_PROFILE_OPTIONS.map((option) => option.value)).toEqual([
      'clean-lines',
      'thin-outline',
      'balanced-cel',
    ])
  })

  it.each([
    ['clean-lines', 15, 30],
    ['thin-outline', 8, 45],
    ['balanced-cel', 25, 20],
  ] as const)('resets %s to its profile defaults', (profile, denoise, edgeBoost) => {
    expect(animeCleanupParamsForProfile(profile)).toEqual({ profile, denoise, edgeBoost })
  })

  it('projects strength constraints from the generated filter schema', () => {
    expect(ANIME_CLEANUP_FIELD_CONSTRAINTS).toEqual({
      denoise: { minimum: 0, maximum: 100 },
      edgeBoost: { minimum: 0, maximum: 100 },
    })
  })
})
