import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MediaItem } from '@/types'

const envStoreState = vi.hoisted(() => ({ current: null as any }))
const mediaStoreState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/env', () => ({
  useEnvStore: () => envStoreState.current,
}))

vi.mock('@/stores/media', () => ({
  useMediaStore: () => mediaStoreState.current,
}))

import InputModuleView from '@/views/InputModuleView.vue'

function createMediaItem(): MediaItem {
  return {
    id: 'item-1',
    inputPath: 'D:/input/demo.mp4',
    displayName: 'demo.mp4',
    selected: true,
    inspecting: false,
    info: {
      type: 'info',
      fps: 24,
      frames: 240,
      duration: 10,
      width: 1920,
      height: 1080,
      hasAudio: true,
      videoCodec: 'hevc',
    },
    issue: null,
    decodeConfig: {
      mode: 'software',
      hwaccel: '',
      hwaccelDevice: '',
      decoder: 'software',
      options: {},
    },
    workflowConfig: {
      fpsMode: 'target',
      processOrder: 'super_resolution_then_interpolation',
      interpolation: {
        enabled: false,
        targetFps: 60,
        multi: 2,
        model: '4.25',
        scale: 1,
        fp16: false,
        tensorBackend: 'pytorch',
        engine: 'cuda',
      },
      superResolution: {
        enabled: false,
        scaleFactor: 2,
        algorithm: 'placeholder',
      },
      anime: {
        enabled: false,
        profile: 'clean-lines',
        denoise: 10,
        edgeBoost: 15,
      },
      preprocess: {
        enabled: false,
        filters: [],
      },
      postprocess: {
        enabled: false,
        filters: [],
      },
    },
    encodeConfig: {
      codec: 'libx264',
      family: 'cpu',
      container: 'mp4',
      keepAudio: true,
      rateControl: { mode: 'crf', value: 18 },
      options: {},
    },
    outputConfig: {
      outputDir: '',
      openOnComplete: false,
      segmentFrames: 1000,
    },
    taskState: {
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
      resumeStatus: null,
    },
    lastOutputPath: '',
  }
}

function createEnvStoreMock() {
  return {
    operationIssue: null,
    clearOperationIssue: vi.fn(),
    setOperationIssue: vi.fn(),
  }
}

function createMediaStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    mediaItems: [createMediaItem()],
    activeItem: createMediaItem(),
    selectedIds: ['item-1'],
    addMediaPaths: vi.fn(),
    inspectItems: vi.fn(),
    ...overrides,
  }
}

describe('InputModuleView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    envStoreState.current = createEnvStoreMock()
    mediaStoreState.current = createMediaStoreMock()
  })

  it('renders media list', () => {
    const wrapper = mount(InputModuleView)
    expect(wrapper.find('.module-stack').exists()).toBe(true)
  })
})
