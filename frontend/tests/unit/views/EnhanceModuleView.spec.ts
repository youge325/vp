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

  it('shows three BasicVSR scales and the non-commercial license notice', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.superResolution.enabled = true
      workflow.superResolution.tensorBackend = 'pytorch'
      workflow.superResolution.algorithm = 'real-rawvsr-basicvsr'
      workflow.superResolution.scaleFactor = 3
    })

    const wrapper = mount(EnhanceModuleView)

    expect(wrapper.text()).toContain('2x')
    expect(wrapper.text()).toContain('3x')
    expect(wrapper.text()).toContain('4x')
    expect(wrapper.text()).toContain('非商业模型')
    expect(wrapper.text()).toContain('仅限非商业研究与个人使用')
    expect(wrapper.get('.model-license-banner a').attributes('href')).toBe(
      'https://github.com/zmzhang1998/Real-RawVSR',
    )
  })

})
