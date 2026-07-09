// pure: no Vue / no Pinia / no Tauri
// Decode/encode form view-state and value correction rules.

import type {
  DecoderProfileSpec,
  EncoderProfileSpec,
  HardwareDeviceOptionSpec,
} from '@/types/domain/capability'
import type { RateControlMode } from '@/types/domain/workflow'
import type { DecodeConfig, EncodeConfig } from '@/types/protocol'
import {
  getDecoderHwaccelDeviceOptions,
  resolveDecoderHwaccelDevice,
} from './decode-hardware'
import {
  getRateControlModeOptions,
  getRateControlUnit,
  hasRateControlModes,
  resolveRateControlForMode,
} from './rate-control'
import type { SelectOption } from './select-options'

const RATE_CONTROL_UNAVAILABLE_HINT = '未探测到可用码率控制模式'

export interface RateControlViewState {
  options: SelectOption[]
  disabled: boolean
  modeHint?: string
  valueHint?: string
}

export function buildDecoderHardwareDeviceOptions(
  profile: Pick<DecoderProfileSpec, 'hardwareDevices'> | null,
): SelectOption[] {
  return (profile?.hardwareDevices ?? []).map((device) => ({
    value: device,
    label: device.toUpperCase(),
  }))
}

export function buildDecoderHardwareDeviceNumberOptions(
  profile: DecoderProfileSpec | null,
  hwaccel: string,
): HardwareDeviceOptionSpec[] {
  return getDecoderHwaccelDeviceOptions(profile, hwaccel)
}

export function applyDecodeHwaccelSelection(
  config: DecodeConfig,
  profile: DecoderProfileSpec | null,
  hwaccel: string,
): DecodeConfig {
  return {
    ...config,
    hwaccel,
    hwaccelDevice: resolveDecoderHwaccelDevice(profile, hwaccel),
  }
}

export function applyDecodeHwaccelDeviceSelection(
  config: DecodeConfig,
  profile: DecoderProfileSpec | null,
  hwaccelDevice: string,
): DecodeConfig {
  return {
    ...config,
    hwaccelDevice: resolveDecoderHwaccelDevice(profile, config.hwaccel ?? '', hwaccelDevice),
  }
}

export function buildRateControlViewState(
  profile: EncoderProfileSpec | null,
  mode: RateControlMode,
): RateControlViewState {
  const disabled = !hasRateControlModes(profile)
  if (disabled) {
    return {
      options: [],
      disabled,
      modeHint: RATE_CONTROL_UNAVAILABLE_HINT,
      valueHint: RATE_CONTROL_UNAVAILABLE_HINT,
    }
  }

  const unit = getRateControlUnit(profile, mode)
  return {
    options: getRateControlModeOptions(profile),
    disabled,
    modeHint: undefined,
    valueHint: unit ? `单位: ${unit}` : undefined,
  }
}

export function resolveRateControlModeSelection(
  profile: EncoderProfileSpec | null,
  mode: RateControlMode,
): EncodeConfig['rateControl'] | null {
  return resolveRateControlForMode(profile, mode)
}

export function normalizeSegmentFrames(value: number): number {
  return Number.isFinite(value) && value > 0 ? Math.round(value) : 1000
}
