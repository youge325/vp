import { ref } from 'vue'
import { describe, expect, it } from 'vitest'

import { createIoProfileState } from '@/composables/forms/io-profile-state'
import type { CodecProfileSpec } from '@/types/protocol'

function profile(name: string, label: string, optionName: string): CodecProfileSpec {
  return {
    name,
    label,
    family: 'software',
    codec: 'h264',
    available: true,
    hardwareDevices: [],
    options: [
      {
        name: optionName,
        label: optionName,
        type: 'string',
        defaultValue: '',
        choices: [],
        min: null,
        max: null,
      },
    ],
  }
}

describe('io profile state', () => {
  it('derives visible profiles, select options, current profile, and capability options', () => {
    const visibleProfiles = ref([
      profile('software', 'Software', 'threads'),
      profile('h264_nvenc', 'NVENC H.264', 'preset'),
    ])
    const selectedName = ref('h264_nvenc')

    const state = createIoProfileState({
      resolveVisibleProfiles: () => visibleProfiles.value,
      selectedProfileName: () => selectedName.value,
    })

    expect(state.visibleProfiles.value.map((entry) => entry.name)).toEqual(['software', 'h264_nvenc'])
    expect(state.profileOptions.value).toEqual([
      { value: 'software', label: 'Software' },
      { value: 'h264_nvenc', label: 'NVENC H.264' },
    ])
    expect(state.currentProfile.value?.name).toBe('h264_nvenc')
    expect(state.capabilityOptions.value.map((option) => option.name)).toEqual(['preset'])

    selectedName.value = 'missing'

    expect(state.currentProfile.value).toBeNull()
    expect(state.capabilityOptions.value).toEqual([])
  })
})
