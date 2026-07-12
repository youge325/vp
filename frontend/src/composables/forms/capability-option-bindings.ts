import { getOptionValue, updateProfileOption } from '@/services/preset/options'
import type { CapabilityOptionSpec, CapabilityValue } from '@/types/protocol'

interface ConfigWithCapabilityOptions {
  options: Record<string, CapabilityValue>
}

interface CapabilityOptionBindingParams<Config extends ConfigWithCapabilityOptions> {
  getConfig: () => Config
  patchConfig: (mutator: (config: Config) => void) => void
}

export function createCapabilityOptionBindings<Config extends ConfigWithCapabilityOptions>({
  getConfig,
  patchConfig,
}: CapabilityOptionBindingParams<Config>) {
  function setOption(name: string, value: CapabilityValue): void {
    patchConfig((config) => {
      config.options = updateProfileOption(config.options, name, value)
    })
  }

  function getOption(option: CapabilityOptionSpec): CapabilityValue {
    return getOptionValue(option, getConfig().options)
  }

  return {
    setOption,
    getOption,
  }
}
