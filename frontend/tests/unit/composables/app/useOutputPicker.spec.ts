import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TASK_ERROR_CODES } from '@/types/protocol'
import { useIssueStore } from '@/stores/issue'
import { useMediaStore } from '@/stores/media'
import { usePresetStore } from '@/stores/preset'
import { createMediaItem } from '@/services/media/factory'
import { codedError } from './errors'
import { createTestPreset } from '../../fixtures/preset'

// useOutputPicker spec(IO 错误路由到 issueStore('encode'))。
//
// 成功路径锁双轨语义:有 activeItem → 写 active + selected
// items 的 outputConfig;无 activeItem → 写 preset.draftPreset.outputConfig。原先直调
// ``presetStore.patchOutput`` 在激活素材态下是真 bug —— view 优先读
// activeItem 的 outputDir,preset 的写入根本不可见。

const pickMock = vi.fn()

vi.mock('@/lib/ipc/endpoints/preset', () => ({
  presetIpc: {
    pickOutputDirectory: () => pickMock(),
    load: vi.fn(),
    save: vi.fn(),
  },
}))

import { useOutputPicker } from '@/composables/app/useOutputPicker'

describe('useOutputPicker', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    pickMock.mockReset()
  })

  it('writes the chosen path to the preset when there is no active item', async () => {
    pickMock.mockResolvedValueOnce('D:/out/picked')
    const issueStore = useIssueStore()
    issueStore.setIssue('encode', {
      code: TASK_ERROR_CODES.IoError,
      message: 'stale failure',
      details: null,
    })
    const presetStore = usePresetStore()

    const picker = useOutputPicker()
    await picker.pickOutputDirectory()

    expect(presetStore.draftPreset.outputConfig.outputDir).toBe('D:/out/picked')
    // 成功路径必须同时清掉上次的 banner
    expect(issueStore.operationIssue).toBeNull()
  })

  // 真 bug 回归护栏。激活素材态下点选择目录,**必须**至少写到
  // active item.outputConfig 而不是 preset.draftPreset,否则 EncodeModuleView 的
  // editorConfig.outputConfig.outputDir 优先读 item,用户看不到变化。
  it('writes the chosen path to the active item when one exists', async () => {
    pickMock.mockResolvedValueOnce('D:/out/picked-item')
    const mediaStore = useMediaStore()
    const presetStore = usePresetStore()
    const item = createMediaItem('/video/a.mp4', createTestPreset())
    mediaStore.appendItems([item])
    mediaStore.setActive(item.id)
    const presetDirBefore = presetStore.draftPreset.outputConfig.outputDir

    const picker = useOutputPicker()
    await picker.pickOutputDirectory()

    // 关键:写到 item,不动 preset
    const itemAfter = mediaStore.findItem(item.id)
    expect(itemAfter?.outputConfig.outputDir).toBe('D:/out/picked-item')
    expect(presetStore.draftPreset.outputConfig.outputDir).toBe(presetDirBefore)
  })

  it('user cancel (null return) clears the banner without touching the preset', async () => {
    pickMock.mockResolvedValueOnce(null)
    const issueStore = useIssueStore()
    issueStore.setIssue('encode', {
      code: TASK_ERROR_CODES.IoError,
      message: 'stale failure',
      details: null,
    })
    const presetStore = usePresetStore()
    const originalDir = presetStore.draftPreset.outputConfig.outputDir

    const picker = useOutputPicker()
    await picker.pickOutputDirectory()

    // preset 没动:取消不该改 outputDir
    expect(presetStore.draftPreset.outputConfig.outputDir).toBe(originalDir)
    // banner 仍要清,否则取消按钮后旧错误挂着误导
    expect(issueStore.operationIssue).toBeNull()
  })

  it('user cancel does not mutate the active item either', async () => {
    pickMock.mockResolvedValueOnce(null)
    const mediaStore = useMediaStore()
    const item = createMediaItem('/video/a.mp4', createTestPreset())
    mediaStore.appendItems([item])
    mediaStore.setActive(item.id)
    const itemDirBefore = item.outputConfig.outputDir

    const picker = useOutputPicker()
    await picker.pickOutputDirectory()

    const itemAfter = mediaStore.findItem(item.id)
    expect(itemAfter?.outputConfig.outputDir).toBe(itemDirBefore)
  })

  it('routes IO errors to issueStore.encode so the IssueBanner picks them up', async () => {
    pickMock.mockRejectedValueOnce(
      codedError(TASK_ERROR_CODES.IoError, 'permission denied'),
    )
    const issueStore = useIssueStore()

    const picker = useOutputPicker()
    await picker.pickOutputDirectory()

    // 关键回归:必须写入 'encode' scope,EncodeModuleView 才能拿到
    expect(issueStore.operationIssue?.scope).toBe('encode')
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.IoError)
    expect(issueStore.operationIssue?.error.message).toContain('permission denied')
  })
})
