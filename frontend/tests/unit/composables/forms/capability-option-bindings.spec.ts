import { reactive } from 'vue'
import { describe, expect, it } from 'vitest'

import { createCapabilityOptionBindings } from '@/composables/forms/capability-option-bindings'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/protocol'

const option: CapabilityOptionSpec = {
  name: 'preset',
  label: 'Preset',
  type: 'string',
  defaultValue: 'medium',
  choices: [],
  min: null,
  max: null,
}

describe('capability option bindings', () => {
  it('reads and patches options through the owning config', () => {
    const config = reactive<{ options: Record<string, CapabilityValue> }>({ options: {} })
    const bindings = createCapabilityOptionBindings({
      getConfig: () => config,
      patchConfig: (mutator) => mutator(config),
    })

    expect(bindings.getOption(option)).toBe('medium')

    bindings.setOption('preset', 'slow')

    expect(config.options).toEqual({ preset: 'slow' })
    expect(bindings.getOption(option)).toBe('slow')
  })
})
