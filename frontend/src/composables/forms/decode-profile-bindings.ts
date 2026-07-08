import { computed, watch, type ComputedRef } from 'vue'

import {
  getVisibleDecoderProfiles,
} from '@/services/preset/profile-picker'
import {
  fallbackUnavailableDecodeProfile,
  selectDecodeProfile,
} from '@/services/preset/profile-selection'
import {
  applyDecodeHwaccelDeviceSelection,
  applyDecodeHwaccelSelection,
  buildDecoderHardwareDeviceNumberOptions,
  buildDecoderHardwareDeviceOptions,
} from '@/services/preset/io-form-rules'
import { buildProfileOptions } from '@/services/preset/io-options'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { DecodeConfig, WorkbenchPreset } from '@/types/protocol'

export interface DecodeProfileBindingParams {
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
  const visibleDecoderProfiles = computed(() =>
    getVisibleDecoderProfiles(checkResult.value, editorVideoCodec.value),
  )
  const decoderProfileOptions = computed(() =>
    buildProfileOptions(visibleDecoderProfiles.value),
  )
  const currentDecoderProfile = computed(() =>
    visibleDecoderProfiles.value.find(
      (profile) => profile.name === editorConfig.value.decodeConfig.decoder,
    ) ?? null,
  )
  const decoderOptions = computed(() => currentDecoderProfile.value?.options ?? [])
  const decoderHardwareDeviceOptions = computed(() =>
    buildDecoderHardwareDeviceOptions(currentDecoderProfile.value),
  )
  const decoderHardwareDeviceNumberOptions = computed(() =>
    buildDecoderHardwareDeviceNumberOptions(
      currentDecoderProfile.value,
      editorConfig.value.decodeConfig.hwaccel ?? '',
    ),
  )

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

  function setDecodeHwaccel(value: string): void {
    patchDecode((config: DecodeConfig) => {
      Object.assign(config, applyDecodeHwaccelSelection(config, currentDecoderProfile.value, value))
    })
  }

  function setDecodeHwaccelDevice(value: string): void {
    patchDecode((config: DecodeConfig) => {
      Object.assign(
        config,
        applyDecodeHwaccelDeviceSelection(config, currentDecoderProfile.value, value),
      )
    })
  }

  return {
    visibleDecoderProfiles,
    decoderProfileOptions,
    currentDecoderProfile,
    decoderOptions,
    decoderHardwareDeviceOptions,
    decoderHardwareDeviceNumberOptions,
    setDecodeProfile,
    setDecodeHwaccel,
    setDecodeHwaccelDevice,
  }
}
