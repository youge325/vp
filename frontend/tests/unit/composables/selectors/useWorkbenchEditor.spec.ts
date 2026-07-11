import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useWorkbenchEditor } from '@/composables/selectors/useWorkbenchEditor'
import { createMediaItem } from '@/services/media/factory'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'

describe('useWorkbenchEditor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('patches selected media items and the draft preset with patchWorkflowAndPreset', () => {
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.processOrder = 'super_resolution_then_interpolation'
    })
    const first = createMediaItem('/video/first.mp4', presetStore.draftPreset)
    const second = createMediaItem('/video/second.mp4', presetStore.draftPreset)
    mediaStore.appendItems([first, second])

    const editor = useWorkbenchEditor()
    editor.patchWorkflowAndPreset((workflow) => {
      workflow.processOrder = 'frame_interpolation_then_super_resolution'
    })

    expect(first.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(second.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(presetStore.draftPreset.workflowConfig.processOrder).toBe('frame_interpolation_then_super_resolution')
  })

  it('patches only the draft preset when no media item is active', () => {
    const presetStore = usePresetStore()
    presetStore.patchWorkflow((workflow) => {
      workflow.preprocess.enabled = false
    })

    const editor = useWorkbenchEditor()
    editor.patchWorkflowAndPreset((workflow) => {
      workflow.preprocess.enabled = true
    })

    expect(presetStore.draftPreset.workflowConfig.preprocess.enabled).toBe(true)
  })
})
