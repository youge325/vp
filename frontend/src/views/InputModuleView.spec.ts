import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { MediaItem } from '@/types'

const storeState = vi.hoisted(() => ({ current: null as any }))

vi.mock('@/stores/workbench', () => ({
  useWorkbenchStore: () => storeState.current,
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
      has_audio: true,
      video_codec: 'hevc',
    },
    issue: null,
    decodeConfig: {
      mode: 'hardware',
      hwaccel: 'cuda',
      hwaccelDevice: '',
      decoder: 'hevc_cuvid',
      options: {},
    },
    workflowConfig: {
      fpsMode: 'target',
      processOrder: 'super_resolution_then_interpolation',
      interpolation: {
        enabled: true,
        targetFps: 60,
        multi: 2,
        model: '4.25',
        scale: 1,
        fp16: false,
        tensorBackend: 'pytorch',
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
    },
    encodeConfig: {
      codec: 'hevc_nvenc',
      family: 'nvidia',
      container: 'mp4',
      keepAudio: true,
      rateControl: {
        mode: 'cq',
        value: 23,
      },
      options: {},
    },
    outputConfig: {
      outputDir: '',
      openOnComplete: true,
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
    },
    lastOutputPath: '',
  }
}

function createStoreMock(overrides: Record<string, unknown> = {}) {
  return {
    ...createStoreMockBase(),
    ...overrides,
  }
}

function createStoreMockBase() {
  const item = createMediaItem()
  return {
    mediaItems: [item],
    activeItem: item,
    activeItemId: item.id,
    selectedIds: [item.id],
    allSelected: true,
    batch: {
      isRunning: false,
    },
    operationIssue: null,
    inspectItems: vi.fn(),
    addMediaPaths: vi.fn(),
    pickInputs: vi.fn(),
    selectAllMedia: vi.fn(),
    setActiveItem: vi.fn(),
    setItemSelected: vi.fn(),
    removeMediaItem: vi.fn(),
  }
}

describe('InputModuleView', () => {
  beforeEach(() => {
    storeState.current = createStoreMock()
  })

  it('keeps import and media-management UI without rendering decode controls', () => {
    const wrapper = mount(InputModuleView)

    expect(wrapper.text()).toContain('批量导入')
    expect(wrapper.text()).toContain('素材列表')
    expect(wrapper.text()).not.toContain('解码设置')
    expect(wrapper.find('.stats-grid').exists()).toBe(false)
    expect(wrapper.findAll('.stat-card')).toHaveLength(0)

    const headers = wrapper.findAll('thead th').map((cell) => cell.text())
    expect(headers).toEqual(['选', '文件', '分辨率', '帧率', '编码', '流程', '状态', '操作'])
  })
})
