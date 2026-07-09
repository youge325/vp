import { createEnhanceEffectBindings } from '@/composables/forms/enhance-effect-bindings'
import { createEnhanceScalarFieldBindings } from '@/composables/forms/enhance-scalar-field-bindings'
import type { EnhanceEffectBindingParams } from '@/composables/forms/enhance-effect-bindings'

type EnhanceFieldBindingParams = EnhanceEffectBindingParams

export function createEnhanceFieldBindings(params: EnhanceFieldBindingParams) {
  return {
    ...createEnhanceEffectBindings(params),
    ...createEnhanceScalarFieldBindings({
      workflow: params.workflow,
      patchWorkflow: params.patchWorkflow,
    }),
  }
}
