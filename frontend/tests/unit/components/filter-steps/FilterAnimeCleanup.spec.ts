import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilterAnimeCleanup from '@/components/filter-steps/FilterAnimeCleanup.vue'

describe('FilterAnimeCleanup', () => {
  it('resets strengths when the profile changes', async () => {
    const wrapper = mount(FilterAnimeCleanup, {
      props: {
        modelValue: {
          kind: 'anime_cleanup',
          enabled: true,
          params: { profile: 'clean-lines', denoise: 99, edgeBoost: 99 },
        },
      },
    })

    await wrapper.find('select').setValue('thin-outline')

    expect(wrapper.emitted('update:modelValue')).toEqual([
      [{
        kind: 'anime_cleanup',
        enabled: true,
        params: { profile: 'thin-outline', denoise: 8, edgeBoost: 45 },
      }],
    ])
  })
})
