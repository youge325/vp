import { test, expect } from '../fixtures'
import { buildSoftwareTaskRequest, captureTauriError } from '../utils/task-runtime'

test.describe('Config validation', () => {
  test('rejects requests that omit required non-nullable contract fields', async ({ tauriPage }) => {
    const inputPath = process.env.VP_E2E_INPUT ?? 'C:/tmp/vp-e2e-test.mp4'
    const request = buildSoftwareTaskRequest(inputPath, 'C:/tmp')
    const missingFields = [
      ['decodeConfig', 'mode'],
      ['workflowConfig', 'interpolation', 'targetFps'],
      ['workflowConfig', 'superResolution', 'numFrames'],
    ] as const

    for (const path of missingFields) {
      const invalidRequest = JSON.parse(JSON.stringify(request)) as Record<string, any>
      const parent = path.slice(0, -1).reduce<Record<string, any>>(
        (value, key) => value[key],
        invalidRequest,
      )
      delete parent[path.at(-1)!]

      const error = await captureTauriError(tauriPage, 'check_resume_state', {
        request: invalidRequest,
      })
      expect(error).not.toBeNull()
      expect(error?.message).toBeTruthy()
    }
  })
})
