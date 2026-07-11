// pure: no Vue / no Pinia / no Tauri
// 编码器/解码器 profile 选优。

import type { DecoderProfileSpec, EncoderProfileSpec } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'

const FAMILY_PRIORITY = ['nvidia', 'intel', 'cpu'] as const
const CODEC_PRIORITY = ['hevc', 'h264', 'av1'] as const

function getEncoderProfiles(env: EnvironmentCheckResult | null): EncoderProfileSpec[] {
  return env?.ffmpeg.encoderProfiles ?? []
}

function getDecoderProfiles(env: EnvironmentCheckResult | null): DecoderProfileSpec[] {
  return env?.ffmpeg.decoderProfiles ?? []
}

export function getVisibleEncoderProfiles(env: EnvironmentCheckResult | null): EncoderProfileSpec[] {
  return getEncoderProfiles(env).filter((profile) => profile.available)
}

export function getVisibleDecoderProfiles(
  env: EnvironmentCheckResult | null,
  videoCodec = '',
): DecoderProfileSpec[] {
  const codec = normalizeCodec(videoCodec)
  return getDecoderProfiles(env).filter((profile) => {
    if (!profile.available) {
      return false
    }
    if (profile.family !== 'software' && profile.hardwareDevices.length === 0) {
      return false
    }
    return profile.codec === 'any' || !codec || profile.codec === codec
  })
}

export function pickPreferredEncoderProfile(env: EnvironmentCheckResult | null): EncoderProfileSpec | null {
  const profiles = getVisibleEncoderProfiles(env)
  for (const family of FAMILY_PRIORITY) {
    const familyProfiles = profiles.filter((profile) => profile.family === family)
    if (familyProfiles.length === 0) {
      continue
    }
    for (const codec of CODEC_PRIORITY) {
      const match = familyProfiles.find((profile) => profile.codec === codec)
      if (match) {
        return match
      }
    }
    return familyProfiles[0] ?? null
  }
  return null
}

export function pickPreferredDecoderProfile(
  env: EnvironmentCheckResult | null,
  videoCodec: string,
): DecoderProfileSpec | null {
  const codec = normalizeCodec(videoCodec)
  const profiles = getVisibleDecoderProfiles(env, codec)
  for (const family of ['nvidia', 'intel'] as const) {
    const match = profiles.find((profile) => profile.family === family)
    if (match) {
      return match
    }
  }
  return profiles.find((profile) => profile.family === 'software') ?? null
}

function normalizeCodec(codec: string): string {
  const lowered = codec.toLowerCase()
  if (lowered.includes('hevc') || lowered.includes('h265')) {
    return 'hevc'
  }
  if (lowered.includes('av1')) {
    return 'av1'
  }
  if (lowered.includes('h264') || lowered.includes('avc')) {
    return 'h264'
  }
  return lowered
}
