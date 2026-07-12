import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilterFields from '@/components/filter-steps/FilterFields.vue'
import { getFilterCatalogEntry } from '@/services/filters/filter-catalog'
import type { FilterStep } from '@/types/protocol'

describe('FilterFields', () => {
  it('renders catalog fields in order with their constraints', () => {
    const step: FilterStep = { kind: 'color', enabled: true, params: {} }
    const wrapper = mount(FilterFields, {
      props: { entry: getFilterCatalogEntry('color'), modelValue: step },
    })
    const inputs = wrapper.findAll('input')

    expect(wrapper.classes()).toContain('field-grid-3')
    expect(inputs.map((input) => input.attributes('value'))).toEqual(['0', '1', '1'])
    expect(inputs[0].attributes()).toMatchObject({ type: 'number', min: '-1', max: '1', step: '0.05' })
  })

  it('updates numeric and text fields without mutating the source step', async () => {
    const step: FilterStep = { kind: 'pad', enabled: true, params: { top: 0, color: '#000000' } }
    const wrapper = mount(FilterFields, {
      props: { entry: getFilterCatalogEntry('pad'), modelValue: step },
    })

    await wrapper.find('input[type="number"]').setValue('12')
    await wrapper.find('input[type="text"]').setValue('#ffffff')

    expect(step.params).toEqual({ top: 0, color: '#000000' })
    const updates = wrapper.emitted('update:modelValue') ?? []
    expect(updates[0]?.[0]).toEqual({ kind: 'pad', enabled: true, params: { top: 12, color: '#000000' } })
    expect(updates[1]?.[0]).toEqual({ kind: 'pad', enabled: true, params: { top: 12, color: '#ffffff' } })
  })
})
