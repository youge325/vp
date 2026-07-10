import { computed, type ComputedRef } from 'vue'

import {
  buildRateControlViewState,
  resolveRateControlModeSelection,
} from '@/services/preset/io-form-rules'
import { toRateControlMode } from '@/services/preset/io-options'
import { toNumberValue } from '@/services/preset/options'
import type { EncoderProfileSpec } from '@/types/domain/capability'
import type { EncodeConfig, WorkbenchPreset } from '@/types/protocol'

interface EncodeRateControlBindingParams {
  currentEncoderProfile: ComputedRef<EncoderProfileSpec | null>
  editorConfig: ComputedRef<Pick<WorkbenchPreset, 'encodeConfig'>>
  patchEncode: (mutator: (config: EncodeConfig) => void) => void
}

export function createEncodeRateControlBindings({
  currentEncoderProfile,
  editorConfig,
  patchEncode,
}: EncodeRateControlBindingParams) {
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
  const rateControlValue = computed(() =>
    toNumberValue(editorConfig.value.encodeConfig.rateControl.value),
  )

  function setRateControlMode(mode: EncodeConfig['rateControl']['mode']): void {
    const rateControl = resolveRateControlModeSelection(currentEncoderProfile.value, mode)
    if (!rateControl) {
      return
    }
    patchEncode((config: EncodeConfig) => {
      config.rateControl = rateControl
    })
  }

  function setRateControlModeValue(value: string): void {
    setRateControlMode(toRateControlMode(value))
  }

  function setRateControlValue(value: number): void {
    patchEncode((config: EncodeConfig) => {
      config.rateControl = { ...config.rateControl, value }
    })
  }

  return {
    rateControlOptions,
    rateControlDisabled,
    rateControlModeHint,
    rateControlValueHint,
    rateControlValue,
    setRateControlMode,
    setRateControlModeValue,
    setRateControlValue,
  }
}
