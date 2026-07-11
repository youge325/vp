// pure: no Vue / no Pinia / no Tauri
// 解码 / 编码配置归一化 — 根据环境探测结果裁剪并补全缺失字段。

import type { DecodeConfig, EncodeConfig } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { createDefaultDecodeConfig, createDefaultEncodeConfig } from './defaults'
import { getVisibleDecoderProfiles, getVisibleEncoderProfiles } from './profile-picker'
import { seedProfileOptions } from './options'
import {
  defaultRateControlValue,
  encoderFamilyFromProfile,
  selectDecodeProfile,
  selectEncodeProfile,
} from './profile-selection'
import {
  hasRateControlModes,
  resolveRateControlForMode,
  resolveRateControlForProfile,
} from './rate-control'

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
    return {
      ...config,
      ...selectDecodeProfile(
        matchedVisible,
        config.options,
        config.hwaccel,
        config.hwaccelDevice,
      ),
    }
  }

  const currentProfile = allProfiles.find((profile) => profile.name === selectedName) ?? null
  const remappedProfile = currentProfile
    ? visibleProfiles.find((profile) => profile.family === currentProfile.family) ?? null
    : null
  if (remappedProfile && remappedProfile.family !== 'software') {
    return {
      ...config,
      ...selectDecodeProfile(remappedProfile, config.options),
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

    const family = encoderFamilyFromProfile(candidate.family)
    return selectEncodeProfile(candidate, config, defaultRateControlValue(family)) ?? config
  }

  const normalizedRateControl =
    hasRateControlModes(matchedProfile)
      ? resolveRateControlForMode(matchedProfile, config.rateControl.mode)
        ?? resolveRateControlForProfile(matchedProfile)
        ?? config.rateControl
      : config.rateControl

  return {
    ...config,
    family: encoderFamilyFromProfile(matchedProfile.family),
    rateControl: normalizedRateControl,
    options: seedProfileOptions(matchedProfile, config.options),
  }
}

export function normalizeOutputDir(value: string): string | null {
  const trimmed = value.trim()
  return trimmed || null
}
