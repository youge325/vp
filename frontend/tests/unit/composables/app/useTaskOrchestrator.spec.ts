import { setActivePinia, createPinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// Phase 7f — verify the module-level singleton's mount/unmount cycle:
// repeated attach calls must NOT register the listener twice, and
// ``disposeRunner`` must let the next cycle start clean (no stale
// runner, no leaked listener handle).

// ``listenTaskEvents`` is what we want to count — vi.hoisted is required
// so the mock is in place before the SUT module evaluates its imports.
const listenMock = vi.hoisted(() =>
  vi.fn(async () => () => {
    /* unlisten noop */
  }),
)

vi.mock('@/lib/ipc/events', () => ({
  listenTaskEvents: listenMock,
}))

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
import type { WorkbenchPreset } from '@/types/protocol'

describe('useTaskOrchestrator singleton', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listenMock.mockClear()
  })

  afterEach(() => {
    // Always tear the singleton down between cases so one test's
    // cached runner can't leak into the next.
    disposeRunner()
  })

  it('only registers the IPC listener once across repeated attach calls', async () => {
    const orchestrator = useTaskOrchestrator()
    await orchestrator.attachTaskListeners()
    await orchestrator.attachTaskListeners()
    await orchestrator.attachTaskListeners()
    expect(listenMock).toHaveBeenCalledTimes(1)
  })

  it('disposeRunner drops the cached runner and the listener handle', async () => {
    // First cycle: attach to register a listener.
    const first = useTaskOrchestrator()
    await first.attachTaskListeners()
    expect(listenMock).toHaveBeenCalledTimes(1)

    // disposeRunner mimics the app-shutdown / test-teardown path.
    disposeRunner()

    // After dispose, a fresh attach must register again — proving the
    // detach handle was actually cleared (otherwise the second
    // ``attachTaskListeners`` would early-return at the idempotency check).
    const second = useTaskOrchestrator()
    await second.attachTaskListeners()
    expect(listenMock).toHaveBeenCalledTimes(2)
  })

  it('survives a Pinia reset between mount cycles when disposeRunner runs', async () => {
    // Simulates the integration-test ``beforeEach`` pattern: tear down
    // Pinia, recreate it, and start over. Without ``disposeRunner`` the
    // module-level cache would still reference the previous Pinia's
    // stores; with it, the second mount sees the fresh stores cleanly.
    const orchestrator = useTaskOrchestrator()
    await orchestrator.attachTaskListeners()

    disposeRunner()
    setActivePinia(createPinia())

    const next = useTaskOrchestrator()
    await next.attachTaskListeners()
    expect(listenMock).toHaveBeenCalledTimes(2)
  })

  // Phase 17 — 锁住 detachTaskListeners + cancelCurrentTask 已下线。production
  // 关停入口是 ``disposeRunner``,task 取消入口是 ``interruptBatch``;两个
  // 独立 export 是 dead surface(useBootstrap 已经改用 disposeRunner)。
  it('does not expose detachTaskListeners after Phase 17', () => {
    const orchestrator = useTaskOrchestrator()
    expect('detachTaskListeners' in orchestrator).toBe(false)
  })

  it('does not expose cancelCurrentTask after Phase 17', () => {
    const orchestrator = useTaskOrchestrator()
    expect('cancelCurrentTask' in orchestrator).toBe(false)
  })
})

// Phase 18 — 启动门禁:outputDir 强制必填,任一 selected item 的
// outputConfig.outputDir 为空 / 纯空白都阻止启动。``cannotStartReason``
// 在按钮 disabled 时给出文案,RenderModuleView 直接显示。
describe('useTaskOrchestrator outputDir gating', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listenMock.mockClear()
  })

  afterEach(() => {
    disposeRunner()
  })

  function seedItem(overrides: { outputDir?: string; selected?: boolean } = {}): void {
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
          autoDownloadWeights: false,
        },
        preprocess: { enabled: false, filters: [] },
        postprocess: { enabled: false, filters: [] },
      },
      encodeConfig: { codec: 'libx265', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
      outputConfig: { outputDir: normalizeOutputDir(overrides.outputDir ?? ''), openOnComplete: true, segmentFrames: 1000 },
    }
    const mediaStore = useMediaStore()
    const item = createMediaItem('/video/a.mp4', samplePreset)
    item.selected = overrides.selected ?? true
    mediaStore.appendItems([item])
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
