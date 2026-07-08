import { computed, type ComputedRef } from 'vue'

import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import { selectEncodeProfile } from '@/services/preset/profile-selection'
import { buildProfileOptions } from '@/services/preset/io-options'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { EncodeConfig, WorkbenchPreset } from '@/types/protocol'

export interface EncodeProfileBindingParams {
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'encodeConfig'>>
  patchEncode: (mutator: (config: EncodeConfig) => void) => void
}

export function createEncodeProfileBindings({
  checkResult,
  editorConfig,
  patchEncode,
}: EncodeProfileBindingParams) {
  const visibleEncoderProfiles = computed(() => getVisibleEncoderProfiles(checkResult.value))
  const encoderProfileOptions = computed(() =>
    buildProfileOptions(visibleEncoderProfiles.value),
  )
  const currentEncoderProfile = computed(() =>
    visibleEncoderProfiles.value.find(
      (profile) => profile.name === editorConfig.value.encodeConfig.codec,
    ) ?? null,
  )
  const encoderOptions = computed(() => currentEncoderProfile.value?.options ?? [])

  function setEncodeProfile(profileName: string): void {
    const profile = visibleEncoderProfiles.value.find((entry) => entry.name === profileName) ?? null
    if (!profile) {
      return
    }
    patchEncode((config: EncodeConfig) => {
      Object.assign(config, selectEncodeProfile(profile, config))
    })
  }

  return {
    visibleEncoderProfiles,
    encoderProfileOptions,
    currentEncoderProfile,
    encoderOptions,
    setEncodeProfile,
  }
}
