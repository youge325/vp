import { test, expect } from './fixtures'

test.describe('Error handling', () => {
  test('inspect_video on missing file returns structured error', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('inspect_video', { inputPath: 'C:/nonexistent/vp-e2e-missing.mp4' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBeTruthy()
    expect(error.message).toBeTruthy()
  })

  test('cancel_task when idle returns InvalidInput', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('cancel_task')
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })

  test('control_task pause when idle returns InvalidInput', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('control_task', { kind: 'pause' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })

  test('control_task resume when idle returns InvalidInput', async ({ tauriPage }) => {
    const error = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        await window.__TAURI_INTERNALS__.invoke('control_task', { kind: 'resume' })
        return null
      } catch (e: any) {
        return { code: e.code, message: e.message }
      }
    })

    expect(error).not.toBeNull()
    expect(error.code).toBe('invalid_input')
  })
})
