import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseToggle from '../BaseToggle.vue'

describe('BaseToggle', () => {
  it('renders the label and chip text', () => {
    const wrapper = mount(BaseToggle, {
      props: { modelValue: false, label: '启用补帧', chipText: 'FP16' },
    })
    expect(wrapper.text()).toContain('启用补帧')
    expect(wrapper.text()).toContain('FP16')
  })

  it('defaults chip text to "启用" when not provided', () => {
    const wrapper = mount(BaseToggle, {
      props: { modelValue: false, label: '保留音频' },
    })
    expect(wrapper.text()).toContain('启用')
  })

  it('reflects modelValue as the checkbox state', async () => {
    const wrapper = mount(BaseToggle, {
      props: { modelValue: true, label: '保留音频' },
    })
    const checkbox = wrapper.find('input[type="checkbox"]')
    expect((checkbox.element as HTMLInputElement).checked).toBe(true)
  })

  it('emits update:modelValue when the checkbox is toggled', async () => {
    const wrapper = mount(BaseToggle, {
      props: { modelValue: false, label: '保留音频' },
    })
    const checkbox = wrapper.find('input[type="checkbox"]')
    await checkbox.setValue(true)
    const events = wrapper.emitted('update:modelValue') ?? []
    expect(events).toEqual([[true]])
  })
})
