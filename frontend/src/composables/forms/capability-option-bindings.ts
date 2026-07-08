import type { ComputedRef } from 'vue'

import { getOptionValue, coerceOptionValue, updateProfileOption } from '@/services/preset/options'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/domain/capability'

export interface CapabilityOptionBindingParams {
  optionValues: ComputedRef<Record<string, CapabilityValue>>
  patchOptions: (options: Record<string, CapabilityValue>) => void
}

export function createCapabilityOptionBindings({
  optionValues,
  patchOptions,
}: CapabilityOptionBindingParams) {
  function setOption(name: string, value: CapabilityValue): void {
    patchOptions(updateProfileOption(optionValues.value, name, value))
  }

  function getOption(option: CapabilityOptionSpec): CapabilityValue {
    return getOptionValue(option, optionValues.value)
  }

  return {
    setOption,
    getOption,
    coerceOptionValue,
  }
}
