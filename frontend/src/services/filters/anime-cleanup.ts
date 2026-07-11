import type { SelectOption } from '@/types/view/select-option'

export type AnimeCleanupProfile = 'clean-lines' | 'thin-outline' | 'balanced-cel'

interface AnimeCleanupParams extends Record<string, string | number | boolean> {
  profile: AnimeCleanupProfile
  denoise: number
  edgeBoost: number
}

const PROFILE_DEFAULTS: Readonly<Record<AnimeCleanupProfile, Readonly<AnimeCleanupParams>>> = {
  'clean-lines': { profile: 'clean-lines', denoise: 15, edgeBoost: 30 },
  'thin-outline': { profile: 'thin-outline', denoise: 8, edgeBoost: 45 },
  'balanced-cel': { profile: 'balanced-cel', denoise: 25, edgeBoost: 20 },
}

export const ANIME_CLEANUP_PROFILE_OPTIONS: readonly SelectOption[] = [
  { value: 'clean-lines', label: '清晰线条' },
  { value: 'thin-outline', label: '细线轮廓' },
  { value: 'balanced-cel', label: '均衡赛璐璐' },
] as const

export function animeCleanupParamsForProfile(profile: AnimeCleanupProfile): AnimeCleanupParams {
  return { ...PROFILE_DEFAULTS[profile] }
}
