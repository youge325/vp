import type { FilterStep } from '@/types/protocol'

interface WritableFilterStep {
  value: FilterStep
}

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

export function createFilterModelParamsPatch(
  model: WritableFilterStep,
): (mutator: (params: FilterStep['params']) => void) => void {
  return createFilterParamsPatch(
    () => model.value,
    (step) => {
      model.value = step
    },
  )
}
