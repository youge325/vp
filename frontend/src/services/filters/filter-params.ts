import type { FilterStep } from '@/types/protocol'

interface WritableFilterStep {
  value: FilterStep
}

export function createFilterModelParamsPatch(
  model: WritableFilterStep,
): (mutator: (params: FilterStep['params']) => void) => void {
  return (mutator) => {
    const current = model.value
    const next: FilterStep = { ...current, params: { ...current.params } }
    mutator(next.params)
    model.value = next
  }
}
