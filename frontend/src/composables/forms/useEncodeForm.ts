// 视图 form-binding — 编码模块。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import {
  defaultRateControlValue,
  seedProfileOptions,
} from '@/services/preset/normalize'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { getOptionValue, coerceOptionValue } from './usePresetEditor'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/view/capability'
import type { EncodeConfig, OutputConfig } from '@/types/protocol'

export function useEncodeForm() {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()
  const { editorConfig } = useWorkbenchEditor()

  const visibleEncoderProfiles = computed(() => getVisibleEncoderProfiles(envStore.env.checkResult))
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
    presetStore.patchEncode((config) => {
      config.codec = profile.name
      config.family =
        profile.family === 'nvidia' || profile.family === 'intel' ? profile.family : 'cpu'
      config.rateControl = defaultRateControlValue(
        profile.family === 'nvidia' || profile.family === 'intel' ? profile.family : 'cpu',
      )
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setRateControlMode(mode: EncodeConfig['rateControl']['mode']): void {
    presetStore.patchEncode((config) => {
      config.rateControl = { mode, value: config.rateControl.value }
    })
  }

  function setRateControlValue(value: number): void {
    presetStore.patchEncode((config) => {
      config.rateControl = { ...config.rateControl, value }
    })
  }

  function setEncodeOption(name: string, value: CapabilityValue): void {
    presetStore.patchEncode((config) => {
      config.options = { ...config.options, [name]: value }
    })
  }

  function getEncodeOption(option: CapabilityOptionSpec): CapabilityValue {
    return getOptionValue(option, editorConfig.value.encodeConfig.options)
  }

  function setContainer(value: string): void {
    presetStore.patchEncode((config) => {
      config.container = value
    })
  }

  function setKeepAudio(value: boolean): void {
    presetStore.patchEncode((config) => {
      config.keepAudio = value
    })
  }

  function setOutputDir(value: string): void {
    presetStore.patchOutput((config) => {
      config.outputDir = value
    })
  }

  function setOpenOnComplete(value: OutputConfig['openOnComplete']): void {
    presetStore.patchOutput((config) => {
      config.openOnComplete = value
    })
  }

  function setSegmentFrames(value: number): void {
    presetStore.patchOutput((config) => {
      config.segmentFrames = Number.isFinite(value) && value > 0 ? Math.round(value) : 1000
    })
  }

  return {
    visibleEncoderProfiles,
    currentEncoderProfile,
    encoderOptions,
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
