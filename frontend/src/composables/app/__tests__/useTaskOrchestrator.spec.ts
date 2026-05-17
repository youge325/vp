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

import { disposeRunner, useTaskOrchestrator } from '@/composables/app/useTaskOrchestrator'

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

  it('detachTaskListeners + re-attach issues a fresh registration', async () => {
    const orchestrator = useTaskOrchestrator()
    await orchestrator.attachTaskListeners()
    orchestrator.detachTaskListeners()
    await orchestrator.attachTaskListeners()
    expect(listenMock).toHaveBeenCalledTimes(2)
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
})
