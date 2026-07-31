import { test, expect } from '../fixtures'
import { invokeTauri } from '../utils/task-runtime'

test.describe('Environment check', () => {
  test('returns the structured probe and then serves the typed cache', async ({ tauriPage }) => {
    const first = await invokeTauri(tauriPage, 'check_environment', { forceRefresh: false })
    expect(['probe', 'cache']).toContain(first.source)
    expect(first.result.ffmpeg.available).toBe(true)
    expect(first.result).toHaveProperty('runtimeMode')
    expect(first.checkedAt).toBeTruthy()

    const cached = await invokeTauri(tauriPage, 'check_environment', { forceRefresh: false })
    expect(cached.source).toBe('cache')
    expect(cached.result.ffmpeg.available).toBe(true)
  })
})
