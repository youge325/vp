import { expect, test } from '../fixtures'
import {
  buildSoftwareTaskRequest,
  disposeTaskEventListeners,
  invokeTauri,
  listenForTaskEvents,
  readTaskEvents,
  waitForTaskEvent,
} from '../utils/task-runtime'
import { createTaskOutputDir, taskInputPath } from '../task/helpers'

test.describe('Invalid encoder contract', () => {
  test('emits one structured task error and no success terminal', async ({ tauriPage }) => {
    const request = buildSoftwareTaskRequest(
      taskInputPath(),
      createTaskOutputDir('invalid-codec'),
    )
    request.encodeConfig.codec = 'definitely-not-a-codec'
    await listenForTaskEvents(tauriPage, ['task-error', 'task-completed', 'task-cancelled'])

    await invokeTauri(tauriPage, 'start_task', { request })
    await waitForTaskEvent(tauriPage, 'task-error', 30000)
    const events = await readTaskEvents(tauriPage)
    const terminals = events.filter((event) =>
      ['task-error', 'task-completed', 'task-cancelled'].includes(event.name),
    )

    expect(terminals.length).toBe(1)
    expect(terminals[0].name).toBe('task-error')
    expect(terminals[0].data.code).toBeTruthy()
    expect(terminals[0].data.message).toBeTruthy()
    await disposeTaskEventListeners(tauriPage)
  })
})
