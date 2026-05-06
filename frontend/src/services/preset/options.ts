// pure: no Vue / no Pinia / no Tauri
// 表单选项纯函数 — getOptionValue / coerceOptionValue。

import type { CapabilityOptionSpec, CapabilityValue } from '@/types/domain/capability'

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
