import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import TaskConsole from './TaskConsole.vue'
import { createMediaItem } from '@/services/media/factory'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { usePresetStore } from '@/stores/preset'

describe('TaskConsole TensorRT logs', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders TensorRT lifecycle log lines with a dedicated class and label', () => {
    const presetStore = usePresetStore()
    const mediaStore = useMediaStore()
    const runStateStore = useMediaRunState()
    const item = createMediaItem('/video/input.mp4', presetStore.draftPreset)
    mediaStore.appendItems([item])
    runStateStore.setTaskState(item.id, {
      status: 'running',
      resumeStatus: null,
      logs: [
        'plain backend log',
        '[VP_TRT] BUILD PaddleGAN ppmsvsr shape=1x5x3x288x640',
      ],
    })

    const wrapper = mount(TaskConsole)
    const lines = wrapper.findAll('.log-line')

    expect(lines[0].classes()).not.toContain('log-line-trt')
    expect(lines[1].classes()).toContain('log-line-trt')
    expect(lines[1].text()).toContain('TensorRT')
    expect(lines[1].text()).toContain('BUILD PaddleGAN ppmsvsr')
  })
})
