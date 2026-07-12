import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilterNumberField from '@/components/filter-steps/FilterNumberField.vue'

describe('FilterNumberField', () => {
  it('preserves numeric input conversion without clamping to declared bounds', async () => {
    const wrapper = mount(FilterNumberField, {
      props: {
        modelValue: 5,
        label: '强度',
        min: 0,
        max: 10,
        step: 0.5,
      },
    })

    const input = wrapper.get('input')
    expect(wrapper.get('label').text()).toContain('强度')
    expect(input.attributes()).toMatchObject({ min: '0', max: '10', step: '0.5' })

    await input.setValue('12.5')

    expect(wrapper.emitted('update:modelValue')).toEqual([[12.5]])
  })
})
