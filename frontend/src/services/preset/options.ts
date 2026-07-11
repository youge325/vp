// pure: no Vue / no Pinia / no Tauri
// 表单选项纯函数 — seed/get/update/coerce option values。

import type { CapabilityOptionSpec, CapabilityValue } from '@/types/protocol'

type ProfileWithOptions = {
  options: Array<{
    name: string
    defaultValue?: CapabilityValue | null
    choices: Array<{ value: CapabilityValue }>
    type: string
  }>
} | null

export function seedProfileOptions(
  profile: ProfileWithOptions,
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

export function updateProfileOption(
  values: Record<string, CapabilityValue>,
  name: string,
  value: CapabilityValue,
): Record<string, CapabilityValue> {
  return { ...values, [name]: value }
}

export function getOptionValue(
  option: { name: string; defaultValue?: CapabilityValue | null; choices: Array<{ value: CapabilityValue }>; type: string },
  values: Record<string, CapabilityValue>,
): CapabilityValue {
  if (option.name in values) {
    return values[option.name] as CapabilityValue
  }
  if (option.defaultValue != null) {
    return option.defaultValue
  }
  if (option.type === 'boolean') {
    return false
  }
  if (option.choices.length > 0) {
    return option.choices[0]?.value ?? ''
  }
  return ''
}

export function coerceOptionValue(option: CapabilityOptionSpec, event: Event): CapabilityValue {
  const target = event.target as HTMLInputElement | HTMLSelectElement
  if (option.type === 'boolean') {
    return (target as HTMLInputElement).checked
  }
  if (option.type === 'number') {
    return Number(target.value)
  }
  return target.value
}

export function toNumberValue(value: unknown): number {
  return Number(value)
}
