// pure: no Vue / no Pinia / no Tauri
// Select option rules for decode/encode views.

import type { CodecProfileSpec } from '@/types/protocol'
import type { SelectOption } from '@/types/view/select-option'

const CONTAINER_OPTIONS = ['mp4', 'mkv', 'mov'] as const

export function buildProfileOptions(profiles: readonly Pick<CodecProfileSpec, 'name' | 'label'>[]): SelectOption[] {
  return profiles.map((profile) => ({ value: profile.name, label: profile.label }))
}

function buildContainerOptions(containers: readonly string[]): SelectOption[] {
  return containers.map((value) => ({ value, label: value.toUpperCase() }))
}

export const CONTAINER_SELECT_OPTIONS: readonly SelectOption[] = buildContainerOptions(CONTAINER_OPTIONS)
