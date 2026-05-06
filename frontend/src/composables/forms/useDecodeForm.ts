// 视图 form-binding — 解码模块。
// 把"切换 profile / 调 hwaccel / 编辑 option"封装成纯方法,业务规则下沉到 services。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import {
  getVisibleDecoderProfiles,
} from '@/services/preset/profile-picker'
import {
  inferHwaccelForProfile,
  seedProfileOptions,
} from '@/services/preset/normalize'
import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { getOptionValue, coerceOptionValue } from './usePresetEditor'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/view/capability'

export function useDecodeForm() {
  const envStore = useEnvStore()
  const presetStore = usePresetStore()
  const { editorConfig, editorVideoCodec } = useWorkbenchEditor()

  const visibleDecoderProfiles = computed(() =>
    getVisibleDecoderProfiles(envStore.env.checkResult, editorVideoCodec.value),
  )
  const currentDecoderProfile = computed(() =>
    visibleDecoderProfiles.value.find(
      (profile) => profile.name === editorConfig.value.decodeConfig.decoder,
    ) ?? null,
  )
  const decoderOptions = computed(() => currentDecoderProfile.value?.options ?? [])

  function setDecodeProfile(profileName: string): void {
    const allProfiles = getVisibleDecoderProfiles(envStore.env.checkResult, '')
    const profile = allProfiles.find((entry) => entry.name === profileName) ?? null
    presetStore.patchDecode((config) => {
      if (!profile || profile.family === 'software') {
        config.mode = 'software'
        config.hwaccel = ''
        config.hwaccelDevice = ''
        config.decoder = 'software'
        config.options = {}
        return
      }
      config.mode = 'hardware'
      config.hwaccel = inferHwaccelForProfile(profile)
      config.decoder = profile.name
      config.options = seedProfileOptions(profile, config.options)
    })
  }

  function setDecodeHwaccelDevice(value: string): void {
    presetStore.patchDecode((config) => {
      config.hwaccelDevice = value
    })
  }

  function setDecodeOption(name: string, value: CapabilityValue): void {
    presetStore.patchDecode((config) => {
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
    setDecodeProfile,
    setDecodeHwaccelDevice,
    setDecodeOption,
    getDecodeOption,
    coerceOptionValue,
  }
}
