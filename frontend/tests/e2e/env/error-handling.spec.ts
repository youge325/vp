import { test, expect } from '../fixtures'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import {
  buildSoftwareTaskRequest,
  captureTauriError,
} from '../utils/task-runtime'

test.describe('Error handling', () => {
  test('returns structured InvalidInput errors for every idle control action', async ({ tauriPage }) => {
    for (const kind of ['pause', 'resume', 'cancel']) {
      const error = await captureTauriError(tauriPage, 'control_task', { kind })
      expect(error).not.toBeNull()
      expect(error?.code).toBe('invalid_input')
      expect(error?.message).toBeTruthy()
    }
  })

  test('preserves structured backend errors for invalid media paths and contents', async ({ tauriPage }) => {
    const missing = await captureTauriError(tauriPage, 'inspect_video', {
      inputPath: 'C:/nonexistent/vp-e2e-missing.mp4',
    })
    expect(missing?.code).toBeTruthy()
    expect(missing?.message).toBeTruthy()

    const { writeFileSync, unlinkSync } = await import('fs')
    const notAVideo = join(tmpdir(), 'vp-e2e-not-a-video.txt')
    writeFileSync(notAVideo, 'this is not a video file')
    const invalid = await captureTauriError(tauriPage, 'inspect_video', { inputPath: notAVideo })
    unlinkSync(notAVideo)
    expect(invalid?.code).toBeTruthy()
    expect(invalid?.message).toBeTruthy()
  })

  test('check_resume_state preserves preflight errors for missing input media', async ({ tauriPage }) => {
    const request = buildSoftwareTaskRequest(
      'C:/nonexistent/vp-e2e-missing.mp4',
      'C:/tmp',
    )
    const error = await captureTauriError(tauriPage, 'check_resume_state', { request })
    expect(error).not.toBeNull()
    expect(error?.code).toBeTruthy()
    expect(error?.message).toBeTruthy()
  })
})
