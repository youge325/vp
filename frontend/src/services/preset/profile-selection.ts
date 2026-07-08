// pure: no Vue / no Pinia / no Tauri
// Decode/encode profile selection rules shared by defaults, normalize, and forms.

import type { CodecFamily } from '@/types/domain/workflow'
import type { DecoderProfileSpec, EncoderProfileSpec, CapabilityValue } from '@/types/domain/capability'
import type { DecodeConfig, EncodeConfig } from '@/types/protocol'
import { resolveDecoderHwaccel, resolveDecoderHwaccelDevice } from './decode-hardware'
import { seedProfileOptions } from './options'
import { resolveRateControlForProfile } from './rate-control'

export function softwareDecodeConfig(): DecodeConfig {
  return {
    mode: 'software',
    hwaccel: '',
    hwaccelDevice: '',
    decoder: 'software',
    options: {},
  }
}

export function selectDecodeProfile(
  profile: DecoderProfileSpec | null,
  currentOptions: Record<string, CapabilityValue> = {},
  preferredHwaccel = '',
  preferredHwaccelDevice = '',
): DecodeConfig {
  if (!profile || profile.family === 'software') {
    return softwareDecodeConfig()
  }

  const hwaccel = resolveDecoderHwaccel(profile, preferredHwaccel)
  return {
    mode: 'hardware',
    hwaccel,
    hwaccelDevice: resolveDecoderHwaccelDevice(profile, hwaccel, preferredHwaccelDevice),
    decoder: profile.name,
    options: seedProfileOptions(profile, currentOptions),
  }
}

export function fallbackUnavailableDecodeProfile(
  profile: DecoderProfileSpec | null,
  mode: DecodeConfig['mode'],
): DecodeConfig | null {
  if (mode !== 'hardware') {
    return null
  }
  if (profile && profile.family !== 'software') {
    return null
  }
  return softwareDecodeConfig()
}

export function encoderFamilyFromProfile(family: CodecFamily): EncodeConfig['family'] {
  return family === 'nvidia' || family === 'intel' ? family : 'cpu'
}

export function defaultRateControlValue(family: EncodeConfig['family']): EncodeConfig['rateControl'] {
  if (family === 'nvidia') {
    return { mode: 'cq', value: 23 }
  }
  if (family === 'intel') {
    return { mode: 'qp', value: 23 }
  }
  return { mode: 'crf', value: 18 }
}

export function selectEncodeProfile(
  profile: EncoderProfileSpec | null,
  config: EncodeConfig,
  fallbackRateControl: EncodeConfig['rateControl'] | null = null,
): EncodeConfig | null {
  if (!profile) {
    return null
  }
  const family = encoderFamilyFromProfile(profile.family)
  return {
    ...config,
    codec: profile.name,
    family,
    rateControl: resolveRateControlForProfile(profile) ?? fallbackRateControl ?? config.rateControl,
    options: seedProfileOptions(profile, config.options),
  }
}
