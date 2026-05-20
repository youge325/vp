// pure: no Vue / no Pinia / no Tauri
// 解码 / 编码配置归一化 — 根据环境探测结果裁剪并补全缺失字段。

import type { DecodeConfig, EncodeConfig } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/domain/env'
import type { CapabilityValue } from '@/types/domain/capability'
import { createDefaultDecodeConfig, createDefaultEncodeConfig } from './defaults'
import { getVisibleDecoderProfiles, getVisibleEncoderProfiles } from './profile-picker'

export function seedProfileOptions(
  profile: { options: Array<{ name: string; defaultValue?: CapabilityValue | null; choices: Array<{ value: CapabilityValue }>; type: string }> } | null,
  currentOptions: Record<string, CapabilityValue> = {},
): Record<string, CapabilityValue> {
  if (!profile) {
    return {}
  }

  const next: Record<string, CapabilityValue> = {}
  for (const option of profile.options) {
    if (option.name in currentOptions) {
      next[option.name] = currentOptions[option.name] as CapabilityValue
      continue
    }
    if (option.defaultValue != null) {
      next[option.name] = option.defaultValue
      continue
    }
    if (option.choices.length > 0) {
      next[option.name] = option.choices[0]?.value ?? ''
      continue
    }
    next[option.name] = option.type === 'boolean' ? false : ''
  }
  return next
}

export function inferHwaccelForProfile(profile: { family: string } | null): string {
  if (!profile) {
    return ''
  }
  if (profile.family === 'nvidia') {
    return 'cuda'
  }
  if (profile.family === 'intel') {
    return 'qsv'
  }
  return ''
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

export function normalizeDecodeConfig(
  config: DecodeConfig,
  checkResult: EnvironmentCheckResult | null,
  videoCodec: string,
  preferDefaults = false,
): DecodeConfig {
  const visibleProfiles = getVisibleDecoderProfiles(checkResult, videoCodec)
  const allProfiles = getVisibleDecoderProfiles(checkResult, '')

  if (preferDefaults) {
    return createDefaultDecodeConfig(checkResult, videoCodec)
  }

  const selectedName = config.mode === 'software' ? 'software' : config.decoder
  const matchedVisible = visibleProfiles.find((profile) => profile.name === selectedName) ?? null
  if (matchedVisible) {
    if (matchedVisible.family === 'software') {
      return {
        mode: 'software',
        hwaccel: '',
        hwaccelDevice: '',
        decoder: 'software',
        options: {},
      }
    }

    return {
      ...config,
      mode: 'hardware',
      hwaccel: inferHwaccelForProfile(matchedVisible),
      hwaccelDevice: config.hwaccelDevice,
      decoder: matchedVisible.name,
      options: seedProfileOptions(matchedVisible, config.options),
    }
  }

  const currentProfile = allProfiles.find((profile) => profile.name === selectedName) ?? null
  const remappedProfile = currentProfile
    ? visibleProfiles.find((profile) => profile.family === currentProfile.family) ?? null
    : null
  if (remappedProfile && remappedProfile.family !== 'software') {
    return {
      ...config,
      mode: 'hardware',
      hwaccel: inferHwaccelForProfile(remappedProfile),
      hwaccelDevice: config.hwaccelDevice,
      decoder: remappedProfile.name,
      options: seedProfileOptions(remappedProfile, config.options),
    }
  }

  return createDefaultDecodeConfig(checkResult, videoCodec)
}

export function normalizeEncodeConfig(
  config: EncodeConfig,
  checkResult: EnvironmentCheckResult | null,
  preferDefaults = false,
): EncodeConfig {
  const profiles = getVisibleEncoderProfiles(checkResult)
  const matchedProfile = profiles.find((profile) => profile.name === config.codec) ?? null

  if (preferDefaults || !matchedProfile) {
    const fallbackProfile = profiles.find((profile) => profile.family === config.family) ?? null
    const defaults = createDefaultEncodeConfig(checkResult)
    const candidate = preferDefaults ? null : fallbackProfile
    if (!candidate) {
      return {
        ...defaults,
        container: config.container || defaults.container,
        keepAudio: config.keepAudio,
      }
    }

    const family =
      candidate.family === 'nvidia' || candidate.family === 'intel' ? candidate.family : 'cpu'
    return {
      ...config,
      codec: candidate.name,
      family,
      rateControl: defaultRateControlValue(family),
      options: seedProfileOptions(candidate, config.options),
    }
  }

  return {
    ...config,
    family:
      matchedProfile.family === 'nvidia' || matchedProfile.family === 'intel'
        ? matchedProfile.family
        : 'cpu',
    options: seedProfileOptions(matchedProfile, config.options),
  }
}

export function normalizeOutputDir(value: string): string | null {
  const trimmed = value.trim()
  return trimmed || null
}
