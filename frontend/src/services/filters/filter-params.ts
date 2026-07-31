import type { FilterStep } from '@/types/protocol'

interface WritableFilterStep<Step extends FilterStep> {
  value: Step
}

export function createFilterModelParamsPatch<Step extends FilterStep>(
  model: WritableFilterStep<Step>,
): (mutator: (params: Step['params']) => void) => void {
  return (mutator) => {
    const current = model.value
    const params: Step['params'] = { ...current.params }
    mutator(params)
    model.value = Object.assign({}, current, { params })
  }
}
