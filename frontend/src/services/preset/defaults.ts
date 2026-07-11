// pure: no Vue / no Pinia / no Tauri
// 默认值工厂 — 根据环境探测结果生成默认的解码/编码/工作流/输出/预设配置。

import type { DecodeConfig, EncodeConfig, OutputConfig, WorkbenchPreset } from '@/types/protocol'
import type { EnvironmentCheckResult } from '@/types/protocol'
import { pickPreferredDecoderProfile, pickPreferredEncoderProfile } from './profile-picker'
import { resolveRateControlForProfile } from './rate-control'
import {
  defaultRateControlValue,
  encoderFamilyFromProfile,
  selectDecodeProfile,
} from './profile-selection'
import {
  createDefaultWorkflowConfigForEnvironment,
} from './workflow-defaults'

// Phase 18 — ``outputDir`` 从 ``string`` 改为 ``string | null``。``null``
// 表示"未选 / 未填",backend Pydantic ``OutputConfig.output_dir`` validator
// (min_length=1 + 非空白)在 wire 入口拒。默认创建预设 / 新 item 时 outputDir
// 是 ``null``,用户必须主动选择目录后才能启动批处理。
function createDefaultOutputConfig(outputDir: string | null = null): OutputConfig {
  return {
    outputDir,
    openOnComplete: true,
    segmentFrames: 1000,
  }
}

export function createDefaultDecodeConfig(
  env: EnvironmentCheckResult | null,
  videoCodec = '',
): DecodeConfig {
  const decoder = pickPreferredDecoderProfile(env, videoCodec)
  return selectDecodeProfile(decoder)
}

export function createDefaultEncodeConfig(env: EnvironmentCheckResult | null): EncodeConfig {
  const profile = pickPreferredEncoderProfile(env)
  const codec = profile?.name ?? 'libx265'
  const family = profile ? encoderFamilyFromProfile(profile.family) : 'cpu'
  const options: Record<string, string | number | boolean> = {}
  const presetOption = profile?.options.find((option) => option.name === 'preset')
  if (presetOption?.defaultValue != null) {
    options.preset = presetOption.defaultValue
  } else if (presetOption?.choices.length) {
    options.preset = presetOption.choices[0]?.value ?? 'medium'
  } else {
    options.preset = family === 'cpu' ? 'medium' : 'p4'
  }

  return {
    codec,
    family,
    container: 'mp4',
    keepAudio: true,
    rateControl: resolveRateControlForProfile(profile) ?? {
      ...defaultRateControlValue(family),
    },
    options,
  }
}

export function createDefaultWorkbenchPreset(env: EnvironmentCheckResult | null): WorkbenchPreset {
  return {
    decodeConfig: createDefaultDecodeConfig(env),
    workflowConfig: createDefaultWorkflowConfigForEnvironment(env),
    encodeConfig: createDefaultEncodeConfig(env),
    outputConfig: createDefaultOutputConfig(),
  }
}
