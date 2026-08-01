import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useStepRailState } from '@/composables/selectors/useStepRailState'
import { useTaskStore } from '@/stores/task'

vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: { module: { key: 'home' } } }),
}))

vi.mock('@/composables/selectors/useWorkbenchEditor', () => ({
  useWorkbenchEditor: () => ({
    editorConfig: {
      value: {
        workflowConfig: {
          preprocess: { enabled: false },
          postprocess: { enabled: false },
        },
      },
    },
  }),
}))

describe('useStepRailState render projection', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps navigation ready for every active batch phase', () => {
    const taskStore = useTaskStore()
    const { moduleStates } = useStepRailState()
    expect(moduleStates.value.render).toBe('idle')

    taskStore.dispatchBatch({ type: 'started', ids: ['a'] })
    taskStore.dispatchBatch({ type: 'queue-advanced', currentId: 'a', remaining: [] })
    expect(moduleStates.value.render).toBe('ready')

    taskStore.dispatchBatch({ type: 'control-requested', kind: 'pause' })
    taskStore.dispatchBatch({ type: 'control-succeeded', kind: 'pause' })
    expect(moduleStates.value.render).toBe('ready')

    taskStore.dispatchBatch({ type: 'control-requested', kind: 'cancel' })
    expect(moduleStates.value.render).toBe('ready')

    taskStore.dispatchBatch({ type: 'item-finalized' })
    expect(moduleStates.value.render).toBe('idle')
  })
})
