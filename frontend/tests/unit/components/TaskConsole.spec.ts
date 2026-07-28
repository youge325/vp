import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import TaskConsole from '@/components/TaskConsole.vue'
import { createMediaItem } from '@/services/media/factory'
import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { usePresetStore } from '@/stores/preset'
import { useTaskStore } from '@/stores/task'

describe('TaskConsole TensorRT logs', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders TensorRT lifecycle log lines in the standard backend log style', () => {
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
        '22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
          '[VP_TRT] TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x288x640',
      ],
    })

    const wrapper = mount(TaskConsole)
    const lines = wrapper.findAll('.log-line')

    expect(lines[0].classes()).not.toContain('log-line-trt')
    expect(lines[1].classes()).not.toContain('log-line-trt')
    expect(lines[1].find('.log-tag').exists()).toBe(false)
    expect(lines[1].text()).toBe(
      '22:03:13 [INFO] app.algorithms.paddle.paddlegan_vsr.runner: ' +
        'TensorRT BUILD PaddleGAN ppmsvsr shape=1x5x3x288x640',
    )
  })

  it('falls back to the active item without mixing in stale current run state', () => {
    const presetStore = usePresetStore()
    const mediaStore = useMediaStore()
    const runStateStore = useMediaRunState()
    const activeItem = createMediaItem('/video/active.mp4', presetStore.draftPreset)
    mediaStore.appendItems([activeItem])
    mediaStore.setActive(activeItem.id)
    runStateStore.setTaskState(activeItem.id, {
      status: 'running',
      resumeStatus: null,
      logs: ['active log'],
    })
    runStateStore.setTaskState('missing-item', {
      status: 'paused',
      resumeStatus: null,
      logs: ['stale log'],
    })
    useTaskStore().setBatch({ currentId: 'missing-item' })

    const wrapper = mount(TaskConsole)

    expect(wrapper.text()).toContain('active log')
    expect(wrapper.text()).not.toContain('stale log')
  })

  it('keeps a completed batch visible as N/N at 100 percent', () => {
    const taskStore = useTaskStore()
    taskStore.setRuntimeIds(['a', 'b'])
    taskStore.setBatch({
      completedCount: 2,
      isRunning: false,
    })

    const wrapper = mount(TaskConsole)

    expect(wrapper.get('.progress-label').text()).toBe('2 / 2')
    expect(wrapper.get('.progress-fill').attributes('style')).toContain('width: 100%')
  })
})
