import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import EnhanceModuleView from '@/views/EnhanceModuleView.vue'
import { useEnvStore } from '@/stores/env'
import { usePresetStore } from '@/stores/preset'
import { createEnhanceEnvironment, createEnvironmentPayload } from '../fixtures/environment'

describe('EnhanceModuleView super-resolution frame wording', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useEnvStore().setCheckPayload(createEnvironmentPayload(createEnhanceEnvironment()))
  })

  it('explains recurrent input frame chunks as distinct from neighbor windows', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'ppmsvsr'
    })

    const wrapper = mount(EnhanceModuleView)

    expect(wrapper.text()).toContain('每块输入帧数')
    expect(wrapper.text()).toContain('每次送入超分模型的连续输入帧数')
    expect(wrapper.text()).toContain('不是邻帧窗口')
  })

  it('shows EDVR fixed neighbor window instead of editable input frame chunks', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'paddle'
      workflow.superResolution.algorithm = 'edvr'
    })

    const wrapper = mount(EnhanceModuleView)

    expect(wrapper.text()).not.toContain('每块输入帧数')
    expect(wrapper.text()).toContain('邻帧窗口')
    expect(wrapper.text()).toContain('5 帧（固定）')
  })

})
