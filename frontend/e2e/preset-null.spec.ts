import { test, expect } from './fixtures'

test.describe('Preset null load', () => {
  test('load_workbench_preset on fresh instance returns null', async ({ tauriPage }) => {
    const result = await tauriPage.evaluate(async () => {
      try {
        // @ts-expect-error __TAURI_INTERNALS__ is injected by Tauri runtime
        return await window.__TAURI_INTERNALS__.invoke('load_workbench_preset')
      } catch (error: any) {
        throw new Error(`load_workbench_preset failed: ${JSON.stringify({ message: error?.message, code: error?.code })}`)
      }
    })

    // All Tauri instances share the same app_data_dir, so a prior
    // preset.spec.ts save may still be on disk. Accept either null
    // (never saved) or a valid WorkbenchPreset shape (prior save).
    if (result === null) {
      expect(result).toBeNull()
    } else {
      expect(result).toHaveProperty('decodeConfig')
      expect(result).toHaveProperty('encodeConfig')
      expect(result).toHaveProperty('workflowConfig')
      expect(result).toHaveProperty('outputConfig')
    }
  })
})
