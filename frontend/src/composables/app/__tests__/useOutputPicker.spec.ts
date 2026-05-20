import { setActivePinia, createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { InvokeError } from '@/lib/ipc/client'
import { TASK_ERROR_CODES } from '@/types/protocol'
import { useIssueStore } from '@/stores/issue'
import { usePresetStore } from '@/stores/preset'

// Phase 16 — useOutputPicker spec
//
// Phase 16 把 ``useOutputPicker`` 的 IO 错误从"由 caller 决定怎么处理"
// 改成"内部直接路由到 ``issueStore.setIssue('encode', …)``"。
// EncodeModuleView 的 ``IssueBanner :issue="useOperationIssue('encode')"``
// 之前从来没有 production writer,本 spec 锁住这条新接通的链路。
//
// 同时锁住"成功路径(含 dialog 取消返回 null)清 banner"的行为 ——
// 否则用户重新点选择按钮后旧错误条会一直挂着。

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

  it('writes the chosen path to the preset and clears any prior encode banner', async () => {
    pickMock.mockResolvedValueOnce('D:/out/picked')
    const issueStore = useIssueStore()
    issueStore.setIssue('encode', {
      code: TASK_ERROR_CODES.IoError,
      message: 'stale failure',
      details: null,
    })
    const presetStore = usePresetStore()

    const picker = useOutputPicker()
    const result = await picker.pickOutputDirectory()

    expect(result.outputDir).toBe('D:/out/picked')
    expect(result.error).toBeNull()
    expect(presetStore.draftPreset.outputConfig.outputDir).toBe('D:/out/picked')
    // 成功路径必须同时清掉上次的 banner
    expect(issueStore.operationIssue).toBeNull()
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
    const result = await picker.pickOutputDirectory()

    expect(result.outputDir).toBeNull()
    expect(result.error).toBeNull()
    // preset 没动:取消不该改 outputDir
    expect(presetStore.draftPreset.outputConfig.outputDir).toBe(originalDir)
    // banner 仍要清,否则取消按钮后旧错误挂着误导
    expect(issueStore.operationIssue).toBeNull()
  })

  it('routes IO errors to issueStore.encode so the IssueBanner picks them up', async () => {
    pickMock.mockRejectedValueOnce(
      new InvokeError(TASK_ERROR_CODES.IoError, 'permission denied'),
    )
    const issueStore = useIssueStore()

    const picker = useOutputPicker()
    const result = await picker.pickOutputDirectory()

    expect(result.outputDir).toBeNull()
    expect(result.error?.code).toBe(TASK_ERROR_CODES.IoError)
    // 关键回归:必须写入 'encode' scope,EncodeModuleView 才能拿到
    expect(issueStore.operationIssue?.scope).toBe('encode')
    expect(issueStore.operationIssue?.error.code).toBe(TASK_ERROR_CODES.IoError)
    expect(issueStore.operationIssue?.error.message).toContain('permission denied')
  })
})
