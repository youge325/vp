import type { SelectOption } from '@/types/view/select-option'
import { APPLICATION_DEFAULTS, FILTER_FIELD_CONSTRAINTS } from '@/types/protocol'
import type { FilterStep } from '@/types/protocol'

type AnimeCleanupFilterStep = Extract<FilterStep, { kind: 'anime_cleanup' }>
type AnimeCleanupParams = AnimeCleanupFilterStep['params']

export type AnimeCleanupProfile = NonNullable<AnimeCleanupParams['profile']>
type AnimeCleanupDefaults = Required<AnimeCleanupParams>

const PROFILE_DEFAULTS = APPLICATION_DEFAULTS.filters.animeCleanup.profiles

const PROFILE_LABELS: Readonly<Record<AnimeCleanupProfile, string>> = {
  'clean-lines': '清晰线条',
  'thin-outline': '细线轮廓',
  'balanced-cel': '均衡赛璐璐',
}

export const ANIME_CLEANUP_PROFILE_OPTIONS: readonly SelectOption<AnimeCleanupProfile>[]
  = FILTER_FIELD_CONSTRAINTS.anime_cleanup.profile.enum.map((profile) => ({
    value: profile,
    label: PROFILE_LABELS[profile],
  }))

export const ANIME_CLEANUP_FIELD_CONSTRAINTS = {
  denoise: FILTER_FIELD_CONSTRAINTS.anime_cleanup.denoise,
  edgeBoost: FILTER_FIELD_CONSTRAINTS.anime_cleanup.edgeBoost,
} as const

export function animeCleanupParamsForProfile(profile: AnimeCleanupProfile): AnimeCleanupDefaults {
  return { profile, ...PROFILE_DEFAULTS[profile] }
}
