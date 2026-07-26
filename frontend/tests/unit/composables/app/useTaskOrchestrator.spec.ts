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
import { useTaskStore } from '@/stores/task'
import { createMediaItem } from '@/services/media/factory'
import { normalizeOutputDir } from '@/services/preset/normalize'
import type { WorkbenchPreset } from '@/types/protocol'

describe('useTaskOrchestrator surface', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    // Always tear the singleton down between cases so one test's
    // cached runner can't leak into the next.
    disposeRunner()
  })

  it('does not expose detachTaskListeners after Phase 17', () => {
    const orchestrator = useTaskOrchestrator()
    expect('detachTaskListeners' in orchestrator).toBe(false)
  })

  it('does not expose cancelCurrentTask after Phase 17', () => {
    const orchestrator = useTaskOrchestrator()
    expect('cancelCurrentTask' in orchestrator).toBe(false)
  })

  it('does not expose the internal current-item projection', () => {
    const orchestrator = useTaskOrchestrator()
    expect('currentTaskItem' in orchestrator).toBe(false)
  })

  it('does not expose listener lifecycle commands', () => {
    const orchestrator = useTaskOrchestrator()
    expect('attachTaskListeners' in orchestrator).toBe(false)
  })
})

// Phase 18 — 启动门禁:outputDir 强制必填,任一 selected item 的
// outputConfig.outputDir 为空 / 纯空白都阻止启动。``cannotStartReason``
// 在按钮 disabled 时给出文案,RenderModuleView 直接显示。
describe('useTaskOrchestrator outputDir gating', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    disposeRunner()
  })

  function seedItem(
    overrides: { outputDir?: string; selected?: boolean; inputPath?: string } = {},
  ) {
    const samplePreset: WorkbenchPreset = {
      decodeConfig: { mode: 'software', hwaccel: '', hwaccelDevice: '', decoder: 'software', options: {} },
      workflowConfig: {
        fpsMode: 'target',
        processOrder: 'super_resolution_then_interpolation',
        interpolation: { enabled: false, targetFps: 60, multi: 2, model: '4.25', onnxModel: '', scale: 1, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
        superResolution: {
          enabled: false,
          scaleFactor: 2,
          algorithm: 'placeholder',
          onnxModel: '',
          tensorBackend: 'onnx',
          engine: 'cuda',
          numFrames: 10,
        },
        preprocess: { enabled: false, filters: [] },
        postprocess: { enabled: false, filters: [] },
      },
      encodeConfig: { codec: 'libx265', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
      outputConfig: { outputDir: normalizeOutputDir(overrides.outputDir ?? ''), openOnComplete: true, segmentFrames: 1000 },
    }
    const mediaStore = useMediaStore()
    const item = createMediaItem(overrides.inputPath ?? '/video/a.mp4', samplePreset)
    item.selected = overrides.selected ?? true
    mediaStore.appendItems([item])
    return item
  }

  it('projects the current batch item and falls back to the active item for a stale id', () => {
    const activeItem = seedItem({
      inputPath: '/video/active.mp4',
      outputDir: 'D:/out',
      selected: false,
    })
    const currentItem = seedItem({
      inputPath: '/video/current.mp4',
      outputDir: 'D:/out',
      selected: false,
    })
    const mediaStore = useMediaStore()
    const taskStore = useTaskStore()
    mediaStore.setActive(activeItem.id)
    taskStore.setBatch({ currentId: currentItem.id })

    const orchestrator = useTaskOrchestrator()
    expect(orchestrator.consoleTaskItem.value?.id).toBe(currentItem.id)

    taskStore.setBatch({ currentId: 'missing-item' })
    expect(orchestrator.consoleTaskItem.value?.id).toBe(activeItem.id)
  })

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
