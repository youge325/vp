import type { FilterStep } from '@/types/protocol'

export function createFilterParamsPatch(
  getStep: () => FilterStep,
  emit: (step: FilterStep) => void,
): (mutator: (params: FilterStep['params']) => void) => void {
  return (mutator) => {
    const current = getStep()
    const next: FilterStep = { ...current, params: { ...current.params } }
    mutator(next.params)
    emit(next)
  }
}
