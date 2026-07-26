// 续传冲突解析 — 处理 resume 冲突对话框,以及 runtime onError 中的 ResumeConflict 错误码。
// 不直接迁移状态机,而是调用 lifecycle 的 hook 来推进队列。

import type { MediaItem, TaskError } from '@/types/domain/media'
import type { ResumeConflictAction } from '@/types/domain/batch'
import type { createCommonHelpers } from './lifecycle/common'
import type { createFinalizeOps } from './lifecycle/finalize'
import type { createQueueOps } from './lifecycle/queue'
import type { BatchLifecycleDeps } from './lifecycle/types'
import { buildResumeConflictDescriptorFromError } from '../resume-classifier'
import { TASK_ERROR_CODES, type ResumeMode } from '@/types/protocol'

type ConflictResolverDeps = Pick<
  BatchLifecycleDeps,
  'getBatch' | 'setBatch' | 'getMediaItem' | 'setPendingConflict'
>
type ConflictLifecycle = Pick<ReturnType<typeof createCommonHelpers>, 'getCurrentTaskContext'> &
  Pick<ReturnType<typeof createQueueOps>, 'launchCurrentItem'> &
  Pick<ReturnType<typeof createFinalizeOps>, 'finalizeCurrent'>

export function createConflictResolver(
  deps: ConflictResolverDeps,
  lifecycle: ConflictLifecycle,
) {
  async function resolveConflict(action: ResumeConflictAction): Promise<void> {
    const batch = deps.getBatch()
    const conflictItem: MediaItem | null = batch.currentId
      ? deps.getMediaItem(batch.currentId)
      : null
    deps.setPendingConflict(null)

    if (!conflictItem) {
      await lifecycle.finalizeCurrent('cancelled')
      return
    }

    if (action === 'cancel') {
      deps.setBatch({ queue: [] })
      await lifecycle.finalizeCurrent('cancelled')
      return
    }

    if (action === 'skip') {
      await lifecycle.finalizeCurrent('cancelled')
      return
    }

    const mode: ResumeMode | undefined = action === 'fresh' ? 'force-fresh' : undefined
    await lifecycle.launchCurrentItem(conflictItem, mode)
  }

  function tryStashFromError(error: TaskError): boolean {
    if (error.code !== TASK_ERROR_CODES.ResumeConflict) {
      return false
    }
    if (!lifecycle.getCurrentTaskContext().item) {
      return false
    }
    deps.setPendingConflict(buildResumeConflictDescriptorFromError(error))
    return true
  }

  return {
    resolveConflict,
    tryStashFromError,
  }
}
