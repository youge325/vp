import type { SelectOption } from '@/types/view/select-option'
import type { FilterStep } from '@/types/protocol'

type AnimeCleanupFilterStep = Extract<FilterStep, { kind: 'anime_cleanup' }>
type AnimeCleanupParams = AnimeCleanupFilterStep['params']

export type AnimeCleanupProfile = NonNullable<AnimeCleanupParams['profile']>
type AnimeCleanupDefaults = Required<AnimeCleanupParams>

const PROFILE_DEFAULTS: Readonly<Record<AnimeCleanupProfile, Readonly<AnimeCleanupDefaults>>> = {
  'clean-lines': { profile: 'clean-lines', denoise: 15, edgeBoost: 30 },
  'thin-outline': { profile: 'thin-outline', denoise: 8, edgeBoost: 45 },
  'balanced-cel': { profile: 'balanced-cel', denoise: 25, edgeBoost: 20 },
}

export const ANIME_CLEANUP_PROFILE_OPTIONS = [
  { value: 'clean-lines', label: '清晰线条' },
  { value: 'thin-outline', label: '细线轮廓' },
  { value: 'balanced-cel', label: '均衡赛璐璐' },
] as const satisfies readonly SelectOption<AnimeCleanupProfile>[]

export function animeCleanupParamsForProfile(profile: AnimeCleanupProfile): AnimeCleanupDefaults {
  return { ...PROFILE_DEFAULTS[profile] }
}
