// 续传冲突解析 — 处理 resume 冲突对话框,以及 runtime onError 中的 ResumeConflict 错误码。
// 不直接迁移状态机,而是调用 lifecycle 的 hook 来推进队列。

import type { MediaItem } from '@/types/domain/media'
import type { ResumeConflictAction } from '@/types/domain/batch'
import type {
  BatchStatePort,
  ConflictCapability,
  FinalizationCapability,
  MediaItemPort,
  QueueContinuation,
  TaskContextCapability,
} from './lifecycle/types'
import { buildResumeConflictDescriptorFromError } from '../resume-classifier'
import { TASK_ERROR_CODES, type ResumeMode, type TaskErrorPayload } from '@/types/protocol'

type ConflictResolverDeps =
  & Pick<BatchStatePort, 'getBatch' | 'dispatchBatch' | 'setPendingConflict'>
  & Pick<MediaItemPort, 'getMediaItem'>
type ConflictLifecycle =
  & TaskContextCapability
  & Pick<QueueContinuation, 'launchCurrentItem'>
  & Pick<FinalizationCapability, 'finalizeCurrent'>

export function createConflictResolver(
  deps: ConflictResolverDeps,
  lifecycle: ConflictLifecycle,
): ConflictCapability {
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
      deps.dispatchBatch({ type: 'queue-cleared' })
      await lifecycle.finalizeCurrent('cancelled')
      return
    }

    if (action === 'skip') {
      await lifecycle.finalizeCurrent('cancelled')
      return
    }

    const mode: ResumeMode = action === 'fresh' ? 'force-fresh' : 'force-resume'
    await lifecycle.launchCurrentItem(conflictItem, mode)
  }

  function tryStashFromError(error: TaskErrorPayload): boolean {
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
