import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseSelect from '@/components/forms/BaseSelect.vue'

const OPTIONS = [
  { value: 'crf', label: 'CRF' },
  { value: 'cq', label: 'CQ' },
  { value: 'bitrate', label: 'Bitrate' },
] as const

describe('BaseSelect', () => {
  it('renders all provided options', () => {
    const wrapper = mount(BaseSelect, {
      props: { modelValue: 'crf', label: '码率模式', options: OPTIONS },
    })
    const optionEls = wrapper.findAll('option')
    expect(optionEls).toHaveLength(3)
    expect(optionEls.map((o) => o.text())).toEqual(['CRF', 'CQ', 'Bitrate'])
  })

  it('reflects the current modelValue as the selected option', () => {
    const wrapper = mount(BaseSelect, {
      props: { modelValue: 'cq', label: '码率模式', options: OPTIONS },
    })
    const select = wrapper.find('select')
    expect((select.element as HTMLSelectElement).value).toBe('cq')
  })

  it('emits update:modelValue when the user changes selection', async () => {
    const wrapper = mount(BaseSelect, {
      props: { modelValue: 'crf', label: '码率模式', options: OPTIONS },
    })
    const select = wrapper.find('select')
    await select.setValue('bitrate')
    const events = wrapper.emitted('update:modelValue') ?? []
    expect(events).toEqual([['bitrate']])
  })
})
