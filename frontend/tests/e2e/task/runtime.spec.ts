import { expect, test } from '../fixtures'
import {
  buildSoftwareTaskRequest,
  captureTauriError,
  disposeTaskEventListeners,
  isTaskEvent,
  invokeTauri,
  listenForTaskEvents,
  readTaskEvents,
  waitForTaskEvent,
} from '../utils/task-runtime'
import { createTaskOutputDir, taskInputPath } from './helpers'
import type { TauriPage } from '../utils/wdio-tauri'
import { TASK_EVENT_NAMES } from '../../../src/types/protocol/events'

const terminalNames = new Set(['task-completed', 'task-error', 'task-cancelled'])

async function runToCompletion(tauriPage: TauriPage, label: string) {
  const request = buildSoftwareTaskRequest(taskInputPath(), createTaskOutputDir(label))
  await listenForTaskEvents(tauriPage, Object.values(TASK_EVENT_NAMES))
  await invokeTauri(tauriPage, 'start_task', { request })
  await waitForTaskEvent(tauriPage, 'task-completed')
  return { request, events: await readTaskEvents(tauriPage) }
}

test.describe('Task runtime supervision', () => {
  test('registers every generated task event including resume status', async ({ tauriPage }) => {
    const names = Object.values(TASK_EVENT_NAMES)
    expect(names).toContain('task-resume-status')

    await listenForTaskEvents(tauriPage)
    const listenerCount = await tauriPage.evaluate(() => {
      return (window as Window & {
        __E2E_UNLISTENERS?: Array<() => Promise<void>>
      }).__E2E_UNLISTENERS?.length ?? 0
    })
    expect(listenerCount).toBe(names.length)
    await disposeTaskEventListeners(tauriPage)
  })

  test('orders progress before one completion and reports a later resume conflict', async ({ tauriPage }) => {
    const { request, events } = await runToCompletion(tauriPage, 'runtime-order')
    const terminals = events.filter((event) => terminalNames.has(event.name))
    const completedIndex = events.findIndex((event) => event.name === 'task-completed')
    const progressIndices = events
      .map((event, index) => event.name === 'task-progress' ? index : -1)
      .filter((index) => index >= 0)

    expect(terminals.length).toBe(1)
    expect(progressIndices.length).toBeGreaterThan(0)
    expect(Math.max(...progressIndices)).toBeLessThan(completedIndex)
    expect(events.some((event) => event.name === 'task-log')).toBe(true)
    const completion = terminals.find(isTaskEvent('task-completed'))
    expect(completion?.data.outputPath).toBeTruthy()
    expect(Number(completion?.data.processedFrames)).toBeGreaterThan(0)

    const resumeState = await invokeTauri(tauriPage, 'check_resume_state', { request })
    expect(resumeState.finalExists).toBe(true)
    await disposeTaskEventListeners(tauriPage)
    await listenForTaskEvents(tauriPage, ['task-error', 'task-completed'])
    await invokeTauri(tauriPage, 'start_task', {
      request: { ...request, resumeMode: 'auto' },
    })
    await waitForTaskEvent(tauriPage, 'task-error', 30000)
    const conflictEvents = await readTaskEvents(tauriPage)
    expect(conflictEvents.length).toBe(1)
    expect(conflictEvents.find(isTaskEvent('task-error'))?.data.code).toBe('resume_conflict')
    await disposeTaskEventListeners(tauriPage)
  })

  test('accepts two sequential starts after each supervisor drains', async ({ tauriPage }) => {
    for (const suffix of ['first', 'second']) {
      const { events } = await runToCompletion(tauriPage, `runtime-sequential-${suffix}`)
      expect(events.filter((event) => terminalNames.has(event.name)).length).toBe(1)
      await disposeTaskEventListeners(tauriPage)
    }
  })

  test('forwards pause and resume to an active process before completion', async ({ tauriPage }) => {
    const request = buildSoftwareTaskRequest(
      taskInputPath(),
      createTaskOutputDir('runtime-pause-resume'),
    )
    request.outputConfig.segmentFrames = 1
    request.workflowConfig.preprocess = {
      enabled: true,
      filters: [{
        kind: 'anime_cleanup',
        enabled: true,
        params: { profile: 'clean-lines', denoise: 15, edgeBoost: 30 },
      }],
    }
    await listenForTaskEvents(tauriPage, ['task-progress', 'task-completed', 'task-error'])
    await invokeTauri(tauriPage, 'start_task', { request })

    let pauseError: { code?: string, message?: string } | null = { code: 'not_attempted' }
    for (let attempt = 0; attempt < 20 && pauseError; attempt += 1) {
      pauseError = await captureTauriError(tauriPage, 'control_task', { kind: 'pause' })
      if (pauseError) {
        await tauriPage.waitForTimeout(25)
      }
    }
    expect(pauseError).toBeNull()
    expect(await captureTauriError(tauriPage, 'control_task', { kind: 'resume' })).toBeNull()
    await waitForTaskEvent(tauriPage, 'task-completed')
    const terminals = (await readTaskEvents(tauriPage))
      .filter((event) => terminalNames.has(event.name))
    expect(terminals.length).toBe(1)
    expect(terminals[0].name).toBe('task-completed')
    await disposeTaskEventListeners(tauriPage)
  })

  test('cancels during startup exactly once and allows the next start', async ({ tauriPage }) => {
    const request = buildSoftwareTaskRequest(
      taskInputPath(),
      createTaskOutputDir('runtime-immediate-cancel'),
    )
    await listenForTaskEvents(tauriPage, ['task-cancelled', 'task-completed', 'task-error'])
    await invokeTauri(tauriPage, 'start_task', { request })
    await invokeTauri(tauriPage, 'control_task', { kind: 'cancel' })
    await waitForTaskEvent(tauriPage, 'task-cancelled', 30000)
    const cancelled = (await readTaskEvents(tauriPage))
      .filter((event) => terminalNames.has(event.name))
    expect(cancelled.length).toBe(1)
    expect(cancelled.find(isTaskEvent('task-cancelled'))?.data.reason).toBe('user')
    await disposeTaskEventListeners(tauriPage)

    const { events } = await runToCompletion(tauriPage, 'runtime-after-cancel')
    expect(events.filter((event) => terminalNames.has(event.name)).length).toBe(1)
    await disposeTaskEventListeners(tauriPage)
  })

  test('rejects a concurrent second start without disturbing cancellation', async ({ tauriPage }) => {
    const request = buildSoftwareTaskRequest(
      taskInputPath(),
      createTaskOutputDir('runtime-double-start'),
    )
    request.workflowConfig.preprocess = {
      enabled: true,
      filters: [{
        kind: 'anime_cleanup',
        enabled: true,
        params: { profile: 'clean-lines', denoise: 15, edgeBoost: 30 },
      }],
    }
    await listenForTaskEvents(tauriPage, ['task-cancelled'])
    await invokeTauri(tauriPage, 'start_task', { request })
    const duplicate = await captureTauriError(tauriPage, 'start_task', { request })
    expect(duplicate?.code).toBe('invalid_input')
    await invokeTauri(tauriPage, 'control_task', { kind: 'cancel' })
    await waitForTaskEvent(tauriPage, 'task-cancelled', 30000)
    await disposeTaskEventListeners(tauriPage)
  })
})
