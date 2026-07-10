// pure: no Vue / no Pinia / no Tauri
// Select option and value conversion rules for decode/encode views.

import type { CodecProfileSpec } from '@/types/domain/capability'
import type { RateControlMode } from '@/types/domain/workflow'
import { CONTAINER_OPTIONS } from '@/config/constants'
import type { SelectOption } from '@/types/view/select-option'

export function buildProfileOptions(profiles: readonly Pick<CodecProfileSpec, 'name' | 'label'>[]): SelectOption[] {
  return profiles.map((profile) => ({ value: profile.name, label: profile.label }))
}

function buildContainerOptions(containers: readonly string[]): SelectOption[] {
  return containers.map((value) => ({ value, label: value.toUpperCase() }))
}

export const CONTAINER_SELECT_OPTIONS: readonly SelectOption[] = buildContainerOptions(CONTAINER_OPTIONS)

export function toRateControlMode(value: string): RateControlMode {
  return value as RateControlMode
}
