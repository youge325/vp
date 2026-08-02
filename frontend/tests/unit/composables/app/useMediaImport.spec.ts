import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TASK_ERROR_CODES } from '@/types/protocol'
import { useIssueStore } from '@/stores/issue'
import { useMediaStore } from '@/stores/media'
import { codedError } from './errors'

// useMediaImport spec。
//
// "导入失败"从 mediaRunState.setIssue(itemId, …)(旧实现
// 引入的 dead write) 改写到 issueStore.setIssue('input', …),InputModuleView
// 的 useOperationIssue('input') 才能真的拿到。本 spec 锁住这条链路:
//
// 1. inspect 抛 → issueStore 的 'input' scope banner 被点亮
// 2. inspect 成功 → 同一 scope 被 clear(避免上一次失败的 banner 卡住)
// 3. importPaths 跳过已存在 path(case-insensitive 去重),不重复触发 inspect
// 4. importPaths 空入参不调用 appendItems / inspect(no-op short-circuit)

const inspectMock = vi.fn()
const pickInputsMock = vi.fn()

vi.mock('@/lib/ipc/endpoints/media', () => ({
  mediaIpc: {
    inspect: (path: string) => inspectMock(path),
    pickInputs: () => pickInputsMock(),
  },
}))

import { useMediaImport } from '@/composables/app/useMediaImport'

function sampleInfo(overrides: Record<string, unknown> = {}) {
  return {
    fps: 24,
    width: 1920,
    height: 1080,
    videoCodec: 'h264',
    ...overrides,
  }
}

describe('useMediaImport', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    inspectMock.mockReset()
    pickInputsMock.mockReset()
  })

  it('routes inspect failures to issueStore.input so IssueBanner picks them up', async () => {
    // 关键回归:必须写入 issueStore('input'),而不是 mediaRunState
    // (后者没有视图侧消费方,原实现中的写入是 dead write)。
    inspectMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.ProcessFailed, 'ffprobe spawn failed'),
    )

    const issueStore = useIssueStore()
    const importer = useMediaImport()

    await importer.importPaths(['/video/broken.mp4'])

    expect(issueStore.getIssue('input')?.code).toBe(TASK_ERROR_CODES.ProcessFailed)
    expect(issueStore.getIssue('input')?.message).toContain('ffprobe spawn failed')
  })

  it('clears any prior input banner before each inspect attempt', async () => {
    // 上一次失败的 banner 不应该卡住下一次成功的 inspect —— 否则用户
    // 重新点"批量导入"后旧错误仍然挂着,体验断裂。
    inspectMock.mockResolvedValueOnce(sampleInfo())

    const issueStore = useIssueStore()
    issueStore.setIssue('input', {
      code: TASK_ERROR_CODES.ProcessFailed,
      message: 'stale failure',
      details: null,
    })

    const importer = useMediaImport()
    await importer.importPaths(['/video/ok.mp4'])

    expect(issueStore.getIssue('input')).toBeNull()
  })

  it('writes info / decodeConfig back to the media item on a successful inspect', async () => {
    inspectMock.mockResolvedValueOnce(sampleInfo({ videoCodec: 'hevc' }))

    const mediaStore = useMediaStore()
    const importer = useMediaImport()
    await importer.importPaths(['/video/clip.mp4'])

    expect(mediaStore.mediaItems).toHaveLength(1)
    const item = mediaStore.mediaItems[0]
    expect(item.inputPath).toBe('/video/clip.mp4')
    expect(item.info?.videoCodec).toBe('hevc')
    // active 应该被设到第一个新 item 上,导入完后 step rail 不会停在
    // null active(否则 Edit 按钮不知道改哪个)。
    expect(mediaStore.activeItemId).toBe(item.id)
    expect(inspectMock).toHaveBeenCalledOnce()
    expect(inspectMock).toHaveBeenCalledWith('/video/clip.mp4')
  })

  it('deduplicates already-imported paths (case-insensitive)', async () => {
    inspectMock.mockResolvedValue(sampleInfo())

    const mediaStore = useMediaStore()
    const importer = useMediaImport()

    await importer.importPaths(['/video/clip.mp4'])
    // 第二次导入同路径(大小写不一致 + 子集重复),应被去重。
    await importer.importPaths(['/Video/CLIP.mp4', '/video/extra.mp4'])

    const paths = mediaStore.mediaItems.map((item) => item.inputPath)
    expect(paths).toEqual(['/video/clip.mp4', '/video/extra.mp4'])
    // 第一次 inspect('/video/clip.mp4') + 第二次 inspect('/video/extra.mp4')
    // 但 /Video/CLIP.mp4 不应该 re-inspect。
    expect(inspectMock).toHaveBeenCalledTimes(2)
    expect(inspectMock).toHaveBeenNthCalledWith(1, '/video/clip.mp4')
    expect(inspectMock).toHaveBeenNthCalledWith(2, '/video/extra.mp4')
  })

  it('importPaths short-circuits on empty / blank-only input', async () => {
    const mediaStore = useMediaStore()
    const importer = useMediaImport()

    await importer.importPaths([])
    await importer.importPaths(['', ''])

    expect(mediaStore.mediaItems).toEqual([])
    expect(inspectMock).not.toHaveBeenCalled()
  })

  it('pickAndImport delegates to pickInputs and imports the selected paths', async () => {
    pickInputsMock.mockResolvedValueOnce(['/video/picked.mp4'])
    inspectMock.mockResolvedValueOnce(sampleInfo())

    const mediaStore = useMediaStore()
    const importer = useMediaImport()
    await importer.pickAndImport()

    expect(mediaStore.mediaItems).toHaveLength(1)
    expect(mediaStore.mediaItems[0].inputPath).toBe('/video/picked.mp4')
  })

  it('pickAndImport routes picker IO errors to the input issue', async () => {
    pickInputsMock.mockRejectedValueOnce(new Error('dialog canceled'))

    const issueStore = useIssueStore()
    const importer = useMediaImport()
    await importer.pickAndImport()

    expect(issueStore.getIssue('input')?.code).toBe(TASK_ERROR_CODES.IoError)
    expect(issueStore.getIssue('input')?.message).toContain('dialog canceled')
  })
})
