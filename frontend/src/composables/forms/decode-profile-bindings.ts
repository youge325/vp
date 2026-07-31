import { watch, type ComputedRef } from 'vue'

import { createIoProfileState } from '@/composables/forms/io-profile-state'
import {
  getVisibleDecoderProfiles,
} from '@/services/preset/profile-picker'
import {
  fallbackUnavailableDecodeProfile,
  selectDecodeProfile,
} from '@/services/preset/profile-selection'
import type { CodecProfileSpec } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'
import type { DecodeConfig, WorkbenchPreset } from '@/types/protocol'

interface DecodeProfileBindingParams {
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'decodeConfig'>>
  editorVideoCodec: ComputedRef<string>
  patchDecode: (mutator: (config: DecodeConfig) => void) => void
}

export function createDecodeProfileBindings({
  checkResult,
  editorConfig,
  editorVideoCodec,
  patchDecode,
}: DecodeProfileBindingParams) {
  const profileState = createIoProfileState<CodecProfileSpec>({
    resolveVisibleProfiles: () => getVisibleDecoderProfiles(checkResult.value, editorVideoCodec.value),
    selectedProfileName: () => editorConfig.value.decodeConfig.decoder ?? '',
  })
  const decoderProfileOptions = profileState.profileOptions
  const currentDecoderProfile = profileState.currentProfile
  const decoderOptions = profileState.capabilityOptions

  watch(
    [
      checkResult,
      currentDecoderProfile,
      () => editorConfig.value.decodeConfig.mode,
      () => editorConfig.value.decodeConfig.decoder,
    ],
    ([resolvedCheckResult, profile, mode]) => {
      const fallback = resolvedCheckResult ? fallbackUnavailableDecodeProfile(profile, mode) : null
      if (!fallback) {
        return
      }
      patchDecode((config: DecodeConfig) => {
        Object.assign(config, fallback)
      })
    },
    { immediate: true },
  )

  function setDecodeProfile(profileName: string): void {
    const allProfiles = getVisibleDecoderProfiles(checkResult.value, '')
    const profile = allProfiles.find((entry) => entry.name === profileName) ?? null
    patchDecode((config: DecodeConfig) => {
      Object.assign(config, selectDecodeProfile(profile, config.options))
    })
  }

  return {
    decoderProfileOptions,
    currentDecoderProfile,
    decoderOptions,
    setDecodeProfile,
  }
}
