import { createEnhanceEffectBindings } from '@/composables/forms/enhance-effect-bindings'
import { createEnhanceScalarFieldBindings } from '@/composables/forms/enhance-scalar-field-bindings'

type EnhanceFieldBindingParams = Parameters<typeof createEnhanceEffectBindings>[0]

export function createEnhanceFieldBindings(params: EnhanceFieldBindingParams) {
  return {
    ...createEnhanceEffectBindings(params),
    ...createEnhanceScalarFieldBindings({
      workflow: params.workflow,
      patchWorkflow: params.patchWorkflow,
    }),
  }
}
