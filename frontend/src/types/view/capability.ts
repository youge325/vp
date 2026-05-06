// 视图层 — 能力选项 view-model(用于 UI 表单渲染的衍生类型)。

import type { CodecFamily } from '../domain/workflow'

export type CapabilityValue = string | number | boolean
export type CapabilityOptionType = 'boolean' | 'number' | 'string' | 'choice'

export interface CapabilityChoice {
  label: string
  value: CapabilityValue
}

export interface CapabilityOptionSpec {
  name: string
  label: string
  type: CapabilityOptionType
  defaultValue: CapabilityValue | null
  choices: CapabilityChoice[]
  min: number | null
  max: number | null
}

export interface CodecProfileSpec {
  name: string
  label: string
  family: CodecFamily
  codec: string
  available: boolean
  pixelFormats: string[]
  hardwareDevices: string[]
  options: CapabilityOptionSpec[]
}

export interface EncoderProfileSpec extends CodecProfileSpec {}
export interface DecoderProfileSpec extends CodecProfileSpec {}
