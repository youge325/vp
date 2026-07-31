import { test, expect } from '../fixtures'
import { buildSoftwareTaskRequest, captureTauriError } from '../utils/task-runtime'
import type { TaskRequest } from '@/types/protocol'

function deleteNestedField(value: Record<string, unknown>, path: readonly string[]): void {
  let parent = value
  for (const key of path.slice(0, -1)) {
    const nested = parent[key]
    if (typeof nested !== 'object' || nested === null || Array.isArray(nested)) {
      throw new Error(`Expected object at ${key}`)
    }
    parent = nested as Record<string, unknown>
  }
  delete parent[path.at(-1)!]
}

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
      const invalidRequest = JSON.parse(JSON.stringify(request)) as Record<string, unknown>
      deleteNestedField(invalidRequest, path)

      const error = await captureTauriError(tauriPage, 'check_resume_state', {
        request: invalidRequest as unknown as TaskRequest,
      })
      expect(error).not.toBeNull()
      expect(error?.message).toBeTruthy()
    }
  })
})
