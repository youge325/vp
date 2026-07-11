import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { beforeEach, describe, expect, it } from 'vitest'

import { useFilterChainForm } from '@/composables/forms/useFilterChainForm'
import { usePresetStore } from '@/stores/preset'

describe('useFilterChainForm', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('tracks route stage changes when the shared stage view is reused', () => {
    const stage = ref<'preprocess' | 'postprocess'>('preprocess')
    const form = useFilterChainForm(stage)
    const preset = usePresetStore()

    form.enabled.value = true
    expect(preset.draftPreset.workflowConfig.preprocess.enabled).toBe(true)
    expect(preset.draftPreset.workflowConfig.postprocess.enabled).toBe(false)

    stage.value = 'postprocess'
    expect(form.enabled.value).toBe(false)

    form.enabled.value = true
    expect(preset.draftPreset.workflowConfig.postprocess.enabled).toBe(true)
  })
})
