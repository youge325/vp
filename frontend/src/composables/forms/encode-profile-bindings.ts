import type { ComputedRef } from 'vue'

import { createIoProfileState } from '@/composables/forms/io-profile-state'
import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import { selectEncodeProfile } from '@/services/preset/profile-selection'
import type { EncoderProfileSpec } from '@/types/domain/capability'
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
  const profileState = createIoProfileState<EncoderProfileSpec>({
    resolveVisibleProfiles: () => getVisibleEncoderProfiles(checkResult.value),
    selectedProfileName: () => editorConfig.value.encodeConfig.codec,
  })
  const visibleEncoderProfiles = profileState.visibleProfiles
  const encoderProfileOptions = profileState.profileOptions
  const currentEncoderProfile = profileState.currentProfile
  const encoderOptions = profileState.capabilityOptions

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
