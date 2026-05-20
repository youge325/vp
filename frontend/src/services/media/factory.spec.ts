import { describe, expect, it } from 'vitest'
import { createMediaItem, createMediaId, basename } from './factory'
import { createIdleTaskState } from '@/services/task/events'
import type { WorkbenchPreset } from '@/types/protocol'

const mockPreset: WorkbenchPreset = {
  decodeConfig: { mode: 'software', hwaccel: '', hwaccelDevice: '', decoder: 'software', options: {} },
  workflowConfig: {
    fpsMode: 'target',
    processOrder: 'super_resolution_then_interpolation',
    interpolation: { enabled: false, targetFps: 60, multi: 2, model: '4.25', onnxModel: '', scale: 1, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
    superResolution: { enabled: false, scaleFactor: 2, algorithm: 'placeholder', onnxModel: '' },
    anime: { enabled: false, profile: 'clean-lines', denoise: 10, edgeBoost: 15 },
    preprocess: { enabled: false, filters: [] },
    postprocess: { enabled: false, filters: [] },
  },
  encodeConfig: { codec: 'libx265', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
  outputConfig: { outputDir: '', openOnComplete: true, segmentFrames: 1000 },
}

describe('createMediaId', () => {
  it('generates a non-empty string', () => {
    const id = createMediaId('/path/to/video.mp4')
    expect(typeof id).toBe('string')
    expect(id.length).toBeGreaterThan(0)
  })

  it('generates unique ids', () => {
    const id1 = createMediaId('/a.mp4')
    const id2 = createMediaId('/b.mp4')
    expect(id1).not.toBe(id2)
  })
})

describe('basename', () => {
  it('extracts filename from path', () => {
    expect(basename('/path/to/video.mp4')).toBe('video.mp4')
    expect(basename('video.mp4')).toBe('video.mp4')
  })
})

describe('createIdleTaskState', () => {
  it('returns idle state with zero progress', () => {
    const state = createIdleTaskState()
    expect(state.status).toBe('idle')
    expect(state.percent).toBe(0)
    expect(state.logs).toEqual([])
  })

  // Phase 16 — ``MediaTaskState.error`` 字段移除。错误展示统一走
  // ``useIssueStore.setIssue('task', …)``,createIdleTaskState 不该
  // 再含 ``error: null``,future 回归不允许偷偷塞回。
  it('does not return an error field after Phase 16', () => {
    const state = createIdleTaskState()
    expect('error' in state).toBe(false)
  })
})

describe('createMediaItem', () => {
  it('creates a media item from path and preset', () => {
    const item = createMediaItem('/path/to/video.mp4', mockPreset)
    expect(item.inputPath).toBe('/path/to/video.mp4')
    expect(item.displayName).toBe('video.mp4')
    expect(item.selected).toBe(true)
    expect(item.decodeConfig.mode).toBe('software')
  })

  // Phase 13.1 — taskState / issue / lastOutputPath 已经从 MediaItem
  // 拆出到独立的 useMediaRunState store,factory 不应再返回这些字段。
  it('does not return run-state fields after Phase 13.1 split', () => {
    const item = createMediaItem('/path/to/video.mp4', mockPreset)
    expect('taskState' in item).toBe(false)
    expect('issue' in item).toBe(false)
    expect('lastOutputPath' in item).toBe(false)
  })
})
