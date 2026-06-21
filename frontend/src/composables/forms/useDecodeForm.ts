// 视图 form-binding — 解码模块。
// 把"切换 profile / 调 hwaccel / 编辑 option"封装成纯方法,业务规则下沉到 services。

import { computed, watch } from 'vue'
import { useEnvStore } from '@/stores/env'
import {
  getVisibleDecoderProfiles,
} from '@/services/preset/profile-picker'
import {
  resolveDecoderHwaccel,
  seedProfileOptions,
} from '@/services/preset/normalize'
import {
  getDecoderHwaccelDeviceOptions,
  resolveDecoderHwaccelDevice,
} from '@/services/preset/decode-hardware'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { getOptionValue, coerceOptionValue } from '@/services/preset/options'
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
    (currentDecoderProfile.value?.hardwareDevices ?? []).map((device) => ({
      value: device,
      label: device.toUpperCase(),
    })),
  )
  const decoderHardwareDeviceNumberOptions = computed(() =>
    getDecoderHwaccelDeviceOptions(
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
      if (!checkResult || mode !== 'hardware' || (profile && profile.family !== 'software')) {
        return
      }
      patchDecode((config: DecodeConfig) => {
        config.mode = 'software'
        config.hwaccel = ''
        config.hwaccelDevice = ''
        config.decoder = 'software'
        config.options = {}
      })
    },
    { immediate: true },
  )

  function setDecodeProfile(profileName: string): void {
    const allProfiles = getVisibleDecoderProfiles(envStore.env.checkResult, '')
    const profile = allProfiles.find((entry) => entry.name === profileName) ?? null
    patchDecode((config: DecodeConfig) => {
      if (!profile || profile.family === 'software') {
        config.mode = 'software'
        config.hwaccel = ''
        config.hwaccelDevice = ''
        config.decoder = 'software'
        config.options = {}
        return
      }
      config.mode = 'hardware'
      const hwaccel = resolveDecoderHwaccel(profile)
      config.hwaccel = hwaccel
      config.hwaccelDevice = resolveDecoderHwaccelDevice(profile, hwaccel)
      config.decoder = profile.name
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setDecodeHwaccel(value: string): void {
    patchDecode((config: DecodeConfig) => {
      config.hwaccel = value
      config.hwaccelDevice = resolveDecoderHwaccelDevice(currentDecoderProfile.value, value)
    })
  }

  function setDecodeHwaccelDevice(value: string): void {
    patchDecode((config: DecodeConfig) => {
      config.hwaccelDevice = resolveDecoderHwaccelDevice(
        currentDecoderProfile.value,
        config.hwaccel ?? '',
        value,
      )
    })
  }

  function setDecodeOption(name: string, value: CapabilityValue): void {
    patchDecode((config: DecodeConfig) => {
      config.options = { ...config.options, [name]: value }
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
