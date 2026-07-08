// 视图 form-binding — 解码模块。
// 把"切换 profile / 调 hwaccel / 编辑 option"封装成纯方法,业务规则下沉到 services。

import { computed, watch } from 'vue'
import { useEnvStore } from '@/stores/env'
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
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { getOptionValue, coerceOptionValue, updateProfileOption } from '@/services/preset/options'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/domain/capability'
import type { DecodeConfig } from '@/types/protocol'

export function useDecodeForm() {
  const envStore = useEnvStore()
  const { editorConfig, editorVideoCodec, patchDecode } = useWorkbenchEditor()

  const visibleDecoderProfiles = computed(() =>
    getVisibleDecoderProfiles(envStore.env.checkResult, editorVideoCodec.value),
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
      () => envStore.env.checkResult,
      currentDecoderProfile,
      () => editorConfig.value.decodeConfig.mode,
      () => editorConfig.value.decodeConfig.decoder,
    ],
    ([checkResult, profile, mode]) => {
      const fallback = checkResult ? fallbackUnavailableDecodeProfile(profile, mode) : null
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
    const allProfiles = getVisibleDecoderProfiles(envStore.env.checkResult, '')
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

  function setDecodeOption(name: string, value: CapabilityValue): void {
    patchDecode((config: DecodeConfig) => {
      config.options = updateProfileOption(config.options, name, value)
    })
  }

  function getDecodeOption(option: CapabilityOptionSpec): CapabilityValue {
    return getOptionValue(option, editorConfig.value.decodeConfig.options)
  }

  return {
    visibleDecoderProfiles,
    currentDecoderProfile,
    decoderOptions,
    decoderHardwareDeviceOptions,
    decoderHardwareDeviceNumberOptions,
    setDecodeProfile,
    setDecodeHwaccel,
    setDecodeHwaccelDevice,
    setDecodeOption,
    getDecodeOption,
    coerceOptionValue,
  }
}
