import { describe, expect, it } from 'vitest'
import * as mediaFactory from '@/services/media/factory'
import { createMediaItem } from '@/services/media/factory'
import { createIdleTaskState } from '@/services/task/events'
import type { WorkbenchPreset } from '@/types/protocol'

const mockPreset: WorkbenchPreset = {
  decodeConfig: { mode: 'software', hwaccel: '', hwaccelDevice: '', decoder: 'software', options: {} },
  workflowConfig: {
    fpsMode: 'target',
    processOrder: 'super_resolution_then_interpolation',
    interpolation: { enabled: false, targetFps: 60, multi: 2, model: '4.25', onnxModel: '', scale: 1, fp16: false, tensorBackend: 'pytorch', engine: 'cuda' },
    superResolution: {
      enabled: false,
      scaleFactor: 2,
      algorithm: 'placeholder',
      onnxModel: '',
      tensorBackend: 'onnx',
      engine: 'cuda',
      numFrames: 10,
    },
    preprocess: { enabled: false, filters: [] },
    postprocess: { enabled: false, filters: [] },
  },
  encodeConfig: { codec: 'libx265', family: 'cpu', container: 'mp4', keepAudio: true, rateControl: { mode: 'crf', value: 18 }, options: {} },
  outputConfig: { outputDir: '', openOnComplete: true, segmentFrames: 1000 },
}

describe('createMediaItem public surface', () => {
  it('keeps id and filename helpers private to the media item factory', () => {
    expect('createMediaId' in mediaFactory).toBe(false)
    expect('basename' in mediaFactory).toBe(false)
  })

  it('generates a non-empty id for each media item', () => {
    const item = createMediaItem('/path/to/video.mp4', mockPreset)
    expect(typeof item.id).toBe('string')
    expect(item.id.length).toBeGreaterThan(0)
  })

  it('generates unique ids for separate media items', () => {
    const first = createMediaItem('/a.mp4', mockPreset)
    const second = createMediaItem('/b.mp4', mockPreset)
    expect(first.id).not.toBe(second.id)
  })

  it('uses the filename portion of the input path as the display name', () => {
    expect(createMediaItem('/path/to/video.mp4', mockPreset).displayName).toBe('video.mp4')
    expect(createMediaItem('video.mp4', mockPreset).displayName).toBe('video.mp4')
  })
})

describe('createIdleTaskState', () => {
  it('returns idle state with empty logs', () => {
    const state = createIdleTaskState()
    expect(state.status).toBe('idle')
    expect(state.logs).toEqual([])
    expect(state.resumeStatus).toBeNull()
  })

  // Phase 16 — ``MediaTaskState.error`` 字段移除。错误展示统一走
  // ``useIssueStore.setIssue('task', …)``,createIdleTaskState 不该
  // 再含 ``error: null``,future 回归不允许偷偷塞回。
  it('does not return an error field after Phase 16', () => {
    const state = createIdleTaskState()
    expect('error' in state).toBe(false)
  })

  // Phase 17 — ``MediaTaskState`` 11 个 dead 字段移除(percent / current /
  // total / stage / stageIndex / stageTotal / processedFrames / timeSeconds /
  // outputPath / startedAt / finishedAt)。锁住 createIdleTaskState 不再
  // 偷偷塞回这些字段。
  it('does not return any of the removed dead progress fields after Phase 17', () => {
    const state = createIdleTaskState()
    for (const field of [
      'percent', 'current', 'total',
      'stage', 'stageIndex', 'stageTotal',
      'processedFrames', 'timeSeconds',
      'outputPath', 'startedAt', 'finishedAt',
    ]) {
      expect(field in state).toBe(false)
    }
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
