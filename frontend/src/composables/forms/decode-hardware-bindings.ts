import { computed, type ComputedRef } from 'vue'

import {
  applyDecodeHwaccelDeviceSelection,
  applyDecodeHwaccelSelection,
  buildDecoderHardwareDeviceNumberOptions,
  buildDecoderHardwareDeviceOptions,
} from '@/services/preset/io-form-rules'
import type { DecoderProfileSpec } from '@/types/domain/capability'
import type { DecodeConfig, WorkbenchPreset } from '@/types/protocol'

export interface DecodeHardwareBindingParams {
  currentDecoderProfile: ComputedRef<DecoderProfileSpec | null>
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'decodeConfig'>>
  patchDecode: (mutator: (config: DecodeConfig) => void) => void
}

export function createDecodeHardwareBindings({
  currentDecoderProfile,
  editorConfig,
  patchDecode,
}: DecodeHardwareBindingParams) {
  const decoderHardwareDeviceOptions = computed(() =>
    buildDecoderHardwareDeviceOptions(currentDecoderProfile.value),
  )
  const decoderHardwareDeviceNumberOptions = computed(() =>
    buildDecoderHardwareDeviceNumberOptions(
      currentDecoderProfile.value,
      editorConfig.value.decodeConfig.hwaccel ?? '',
    ),
  )

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
    decoderHardwareDeviceOptions,
    decoderHardwareDeviceNumberOptions,
    setDecodeHwaccel,
    setDecodeHwaccelDevice,
  }
}
