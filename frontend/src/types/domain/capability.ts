// 领域层 — 能力探测模型(后端探测出的编解码 profile 与可调选项)。
// 这些类型源自后端运行时探测,不是 UI 衍生类型。

import type { CodecFamily } from './workflow'

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
