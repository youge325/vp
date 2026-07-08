import { computed, type ComputedRef } from 'vue'

import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import { normalizeOutputDir } from '@/services/preset/normalize'
import { selectEncodeProfile } from '@/services/preset/profile-selection'
import {
  buildRateControlViewState,
  normalizeSegmentFrames,
  resolveRateControlModeSelection,
} from '@/services/preset/io-form-rules'
import { getOptionValue, coerceOptionValue, updateProfileOption } from '@/services/preset/options'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/domain/capability'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { EncodeConfig, OutputConfig, WorkbenchPreset } from '@/types/protocol'

export interface EncodeFormBindingParams {
  checkResult: ComputedRef<EnvironmentCheckResult | null>
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'encodeConfig' | 'outputConfig'>>
  patchEncode: (mutator: (config: EncodeConfig) => void) => void
  patchOutput: (mutator: (config: OutputConfig) => void) => void
}

export function createEncodeFormBindings({
  checkResult,
  editorConfig,
  patchEncode,
  patchOutput,
}: EncodeFormBindingParams) {
  const visibleEncoderProfiles = computed(() => getVisibleEncoderProfiles(checkResult.value))
  const currentEncoderProfile = computed(() =>
    visibleEncoderProfiles.value.find(
      (profile) => profile.name === editorConfig.value.encodeConfig.codec,
    ) ?? null,
  )
  const encoderOptions = computed(() => currentEncoderProfile.value?.options ?? [])
  const rateControlViewState = computed(() =>
    buildRateControlViewState(
      currentEncoderProfile.value,
      editorConfig.value.encodeConfig.rateControl.mode,
    ),
  )
  const rateControlOptions = computed(() => rateControlViewState.value.options)
  const rateControlDisabled = computed(() => rateControlViewState.value.disabled)
  const rateControlModeHint = computed(() => rateControlViewState.value.modeHint)
  const rateControlValueHint = computed(() => rateControlViewState.value.valueHint)

  function setEncodeProfile(profileName: string): void {
    const profile = visibleEncoderProfiles.value.find((entry) => entry.name === profileName) ?? null
    if (!profile) {
      return
    }
    patchEncode((config: EncodeConfig) => {
      Object.assign(config, selectEncodeProfile(profile, config))
    })
  }

  function setRateControlMode(mode: EncodeConfig['rateControl']['mode']): void {
    const rateControl = resolveRateControlModeSelection(currentEncoderProfile.value, mode)
    if (!rateControl) {
      return
    }
    patchEncode((config: EncodeConfig) => {
      config.rateControl = rateControl
    })
  }

  function setRateControlValue(value: number): void {
    patchEncode((config: EncodeConfig) => {
      config.rateControl = { ...config.rateControl, value }
    })
  }

  function setEncodeOption(name: string, value: CapabilityValue): void {
    patchEncode((config: EncodeConfig) => {
      config.options = updateProfileOption(config.options, name, value)
    })
  }

  function getEncodeOption(option: CapabilityOptionSpec): CapabilityValue {
    return getOptionValue(option, editorConfig.value.encodeConfig.options)
  }

  function setContainer(value: string): void {
    patchEncode((config: EncodeConfig) => {
      config.container = value
    })
  }

  function setKeepAudio(value: boolean): void {
    patchEncode((config: EncodeConfig) => {
      config.keepAudio = value
    })
  }

  function setOutputDir(value: string): void {
    patchOutput((config: OutputConfig) => {
      config.outputDir = normalizeOutputDir(value)
    })
  }

  function setOpenOnComplete(value: OutputConfig['openOnComplete']): void {
    patchOutput((config: OutputConfig) => {
      config.openOnComplete = value
    })
  }

  function setSegmentFrames(value: number): void {
    patchOutput((config: OutputConfig) => {
      config.segmentFrames = normalizeSegmentFrames(value)
    })
  }

  return {
    visibleEncoderProfiles,
    currentEncoderProfile,
    encoderOptions,
    rateControlOptions,
    rateControlDisabled,
    rateControlModeHint,
    rateControlValueHint,
    setEncodeProfile,
    setRateControlMode,
    setRateControlValue,
    setEncodeOption,
    getEncodeOption,
    setContainer,
    setKeepAudio,
    setOutputDir,
    setOpenOnComplete,
    setSegmentFrames,
    coerceOptionValue,
  }
}
