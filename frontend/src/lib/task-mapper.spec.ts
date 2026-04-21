import { describe, expect, it } from 'vitest'
import { buildTaskRequest, buildSummarySections } from '@/lib/task-mapper'
import type { WorkbenchStateSnapshot } from '@/types'

function makeSnapshot(): WorkbenchStateSnapshot {
  return {
    env: {
      lastCheckedAt: null,
      isChecking: false,
      checkResult: null,
      issue: null,
    },
    source: {
      inputPath: 'D:/input/demo.mp4',
      inspecting: false,
      info: {
        type: 'info',
        fps: 24,
        frames: 240,
        duration: 10,
        width: 1920,
        height: 1080,
        has_audio: true,
      },
    },
    workflow: {
      primaryMode: 'frame_interpolation',
      enableInterpolation: true,
      enableSuperResolution: true,
      processOrder: 'frame_interpolation_then_super_resolution',
      fpsMode: 'target',
    },
    interpolation: {
      targetFps: 60,
      multi: 2,
      model: '4.25',
      scale: 1,
      fp16: true,
      tensorBackend: 'pytorch',
    },
    superResolution: {
      enabled: true,
      scaleFactor: 2,
      algorithm: 'placeholder',
    },
    anime: {
      enabled: false,
      profile: 'clean-lines',
      denoise: 10,
      edgeBoost: 15,
    },
    format: {
      remuxOnly: false,
      keepAudio: true,
      container: 'mp4',
    },
    encode: {
      codec: 'libx264',
      crf: 18,
      preset: 'medium',
    },
    output: {
      outputPath: 'D:/output/demo_processed.mp4',
      outputDir: '',
      tempDir: '',
      openOnComplete: true,
    },
    task: {
      status: 'idle',
      percent: 0,
      current: 0,
      total: 0,
      stage: '',
      stageIndex: 0,
      stageTotal: 0,
      logs: [],
      outputPath: '',
      processedFrames: 0,
      timeSeconds: 0,
      error: null,
      startedAt: null,
      finishedAt: null,
    },
  }
}

describe('task mapper', () => {
  it('builds a combined task request', () => {
    const request = buildTaskRequest(makeSnapshot())

    expect(request.algorithm).toBe('frame_interpolation')
    expect(request.enableInterpolation).toBe(true)
    expect(request.enableSuperResolution).toBe(true)
    expect(request.processOrder).toBe('frame_interpolation_then_super_resolution')
    expect(request.targetFps).toBe(60)
  })

  it('builds summary sections for the sidebar', () => {
    const sections = buildSummarySections(makeSnapshot())
    expect(sections).toHaveLength(5)
    expect(sections[0]?.title).toBe('素材')
    expect(sections[1]?.lines[0]).toContain('视频补帧')
  })
})
