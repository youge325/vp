import { setActivePinia, createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Avoid initialising the real Tauri IPC endpoints in tests.
vi.mock('@/lib/ipc/endpoints/task', () => ({
  taskIpc: {
    start: vi.fn(),
    cancel: vi.fn(),
    pause: vi.fn(),
    resume: vi.fn(),
    checkResume: vi.fn(),
    openOutputLocation: vi.fn(),
  },
}))

import { disposeRunner } from '@/composables/app/taskOrchestratorRuntime'
import { useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'
import { useMediaStore } from '@/stores/media'
import { createMediaItem } from '@/services/media/factory'
import { normalizeOutputDir } from '@/services/preset/normalize'
import { createTestPreset } from '../../fixtures/preset'

describe('useTaskOrchestrator', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    disposeRunner()
  })

  function seedItem(
    overrides: { outputDir?: string; selected?: boolean; inputPath?: string } = {},
  ) {
    const samplePreset = createTestPreset({
      outputDir: normalizeOutputDir(overrides.outputDir ?? ''),
    })
    const mediaStore = useMediaStore()
    const item = createMediaItem(overrides.inputPath ?? '/video/a.mp4', samplePreset)
    item.selected = overrides.selected ?? true
    mediaStore.appendItems([item])
    return item
  }

  it('canStartBatch is false when selected item has empty outputDir', () => {
    seedItem({ outputDir: '' })
    const orchestrator = useTaskOrchestrator()
    expect(orchestrator.canStartBatch.value).toBe(false)
    expect(orchestrator.cannotStartReason.value).toMatch(/输出目录/)
  })

  it('canStartBatch is false when outputDir is whitespace-only', () => {
    seedItem({ outputDir: '   \t  ' })
    const orchestrator = useTaskOrchestrator()
    expect(orchestrator.canStartBatch.value).toBe(false)
    expect(orchestrator.cannotStartReason.value).toMatch(/输出目录/)
  })

  it('canStartBatch is true when outputDir is a valid path', () => {
    seedItem({ outputDir: 'D:/out' })
    const orchestrator = useTaskOrchestrator()
    expect(orchestrator.canStartBatch.value).toBe(true)
    expect(orchestrator.cannotStartReason.value).toBeNull()
  })

  it('cannotStartReason reports "no item selected" when nothing is selected', () => {
    const orchestrator = useTaskOrchestrator()
    // No items at all — should be the "no item" reason, not outputDir.
    expect(orchestrator.canStartBatch.value).toBe(false)
    expect(orchestrator.cannotStartReason.value).toMatch(/勾选/)
  })
})
