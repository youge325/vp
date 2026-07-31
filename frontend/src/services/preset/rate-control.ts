// pure: no Vue / no Pinia / no Tauri
// 码率控制模式来源于后端 FFmpeg 二次探测后的 rateControlModes。

import type { CodecProfileSpec, RateControlModeSpec } from '@/types/protocol'
import type { RateControlMode } from '@/types/protocol'
import type { EncodeConfig } from '@/types/protocol'
import type { SelectOption } from '@/types/view/select-option'

function getProfileModes(profile: CodecProfileSpec | null): RateControlModeSpec[] {
  return Array.isArray(profile?.rateControlModes) ? profile.rateControlModes : []
}

export function hasRateControlModes(profile: CodecProfileSpec | null): boolean {
  return getProfileModes(profile).length > 0
}

export function getRateControlModeOptions(profile: CodecProfileSpec | null): SelectOption[] {
  return getProfileModes(profile).map((mode) => ({ value: mode.mode, label: mode.label }))
}

export function resolveRateControlForProfile(
  profile: CodecProfileSpec | null,
): EncodeConfig['rateControl'] | null {
  const firstMode = getProfileModes(profile)[0] ?? null
  if (!firstMode) {
    return null
  }
  return { mode: firstMode.mode, value: firstMode.defaultValue }
}

export function resolveRateControlForMode(
  profile: CodecProfileSpec | null,
  mode: RateControlMode,
): EncodeConfig['rateControl'] | null {
  const matched = getProfileModes(profile).find((entry) => entry.mode === mode) ?? null
  if (!matched) {
    return null
  }
  return { mode: matched.mode, value: matched.defaultValue }
}

export function getRateControlUnit(
  profile: CodecProfileSpec | null,
  mode: RateControlMode,
): string | null {
  return getProfileModes(profile).find((entry) => entry.mode === mode)?.unit ?? null
}
