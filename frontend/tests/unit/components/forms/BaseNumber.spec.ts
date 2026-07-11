import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import BaseNumber from '@/components/forms/BaseNumber.vue'

function emittedNumbers(wrapper: ReturnType<typeof mount>): number[] {
  const events = wrapper.emitted('update:modelValue') ?? []
  return events.map((event) => event[0] as number)
}

describe('BaseNumber', () => {
  it('renders the label and current value', () => {
    const wrapper = mount(BaseNumber, {
      props: { modelValue: 42, label: '帧数' },
    })
    expect(wrapper.text()).toContain('帧数')
    const input = wrapper.find('input[type="number"]')
    expect((input.element as HTMLInputElement).valueAsNumber).toBe(42)
  })

  it('emits update:modelValue with the parsed numeric value on input', async () => {
    const wrapper = mount(BaseNumber, {
      props: { modelValue: 10, label: '帧数' },
    })
    const input = wrapper.find('input[type="number"]')
    await input.setValue(25)
    expect(emittedNumbers(wrapper)).toEqual([25])
  })

  it('clamps below the provided min', async () => {
    const wrapper = mount(BaseNumber, {
      props: { modelValue: 10, label: '帧数', min: 5 },
    })
    const input = wrapper.find('input[type="number"]')
    await input.setValue(2)
    expect(emittedNumbers(wrapper)).toEqual([5])
  })

  it('clamps above the provided max', async () => {
    const wrapper = mount(BaseNumber, {
      props: { modelValue: 10, label: '帧数', max: 100 },
    })
    const input = wrapper.find('input[type="number"]')
    await input.setValue(250)
    expect(emittedNumbers(wrapper)).toEqual([100])
  })

  it('does not emit when input value is empty (NaN)', async () => {
    const wrapper = mount(BaseNumber, {
      props: { modelValue: 10, label: '帧数' },
    })
    const input = wrapper.find('input[type="number"]')
    // Simulate clearing the field: valueAsNumber → NaN.
    ;(input.element as HTMLInputElement).value = ''
    await input.trigger('input')
    expect(emittedNumbers(wrapper)).toEqual([])
  })

  it('renders error slot when error prop is provided', () => {
    const wrapper = mount(BaseNumber, {
      props: { modelValue: 1, label: '帧数', error: '超出范围' },
    })
    expect(wrapper.text()).toContain('超出范围')
  })
})
