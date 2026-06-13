// 视图 form-binding — 编码模块。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { getVisibleEncoderProfiles } from '@/services/preset/profile-picker'
import {
  normalizeOutputDir,
  seedProfileOptions,
} from '@/services/preset/normalize'
import {
  getRateControlModeOptions,
  getRateControlUnit,
  hasRateControlModes,
  resolveRateControlForMode,
  resolveRateControlForProfile,
} from '@/services/preset/rate-control'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { getOptionValue, coerceOptionValue } from '@/services/preset/options'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/domain/capability'
import type { EncodeConfig, OutputConfig } from '@/types/protocol'

export function useEncodeForm() {
  const envStore = useEnvStore()
  const { editorConfig, patchEncode, patchOutput } = useWorkbenchEditor()

  const visibleEncoderProfiles = computed(() => getVisibleEncoderProfiles(envStore.env.checkResult))
  const currentEncoderProfile = computed(() =>
    visibleEncoderProfiles.value.find(
      (profile) => profile.name === editorConfig.value.encodeConfig.codec,
    ) ?? null,
  )
  const encoderOptions = computed(() => currentEncoderProfile.value?.options ?? [])
  const rateControlOptions = computed(() => getRateControlModeOptions(currentEncoderProfile.value))
  const rateControlDisabled = computed(() => !hasRateControlModes(currentEncoderProfile.value))
  const rateControlModeHint = computed(() =>
    rateControlDisabled.value ? '未探测到可用码率控制模式' : undefined,
  )
  const rateControlValueHint = computed(() => {
    if (rateControlDisabled.value) {
      return '未探测到可用码率控制模式'
    }
    const unit = getRateControlUnit(
      currentEncoderProfile.value,
      editorConfig.value.encodeConfig.rateControl.mode,
    )
    return unit ? `单位: ${unit}` : undefined
  })

  function setEncodeProfile(profileName: string): void {
    const profile = visibleEncoderProfiles.value.find((entry) => entry.name === profileName) ?? null
    if (!profile) {
      return
    }
    patchEncode((config: EncodeConfig) => {
      config.codec = profile.name
      config.family =
        profile.family === 'nvidia' || profile.family === 'intel' ? profile.family : 'cpu'
      const rateControl = resolveRateControlForProfile(profile)
      if (rateControl) {
        config.rateControl = rateControl
      }
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setRateControlMode(mode: EncodeConfig['rateControl']['mode']): void {
    const rateControl = resolveRateControlForMode(currentEncoderProfile.value, mode)
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
      config.options = { ...config.options, [name]: value }
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
    // Phase 18 — outputDir 必填。trim 防止用户输入纯空格通过 canStartBatch
    // 的 ``Boolean(...)`` 检查;trim 后空时存 null(Phase 18.C 后 wire 形状
    // 是 ``string | null``),view 层据此显示红边 + 提示。
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
      config.segmentFrames = Number.isFinite(value) && value > 0 ? Math.round(value) : 1000
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
