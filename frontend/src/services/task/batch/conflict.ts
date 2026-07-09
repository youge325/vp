// 续传冲突解析 — 处理 resume 冲突对话框,以及 runtime onError 中的 ResumeConflict 错误码。
// 不直接迁移状态机,而是调用 lifecycle 的 hook 来推进队列。

import type { MediaItem, TaskError } from '@/types/domain/media'
import type { ResumeConflictAction, ResumeMode } from '@/types/domain/batch'
import type { BatchLifecycle, BatchLifecycleDeps } from './lifecycle'
import { buildInspectionFromError } from '../resume-classifier'
import { TASK_ERROR_CODES } from '@/types/protocol'

type ConflictResolverDeps = Pick<
  BatchLifecycleDeps,
  'getBatch' | 'setBatch' | 'getMediaItem' | 'setPendingConflict'
>

interface ConflictResolver {
  resolveConflict(action: ResumeConflictAction): Promise<void>
  /**
   * 尝试把 ``TaskError`` 解析为续传冲突;返回 ``true`` 表示已暂存为待解决冲突,
   * 调用方应停止后续错误传播。
   */
  tryStashFromError(error: TaskError): boolean
}

export function createConflictResolver(
  deps: ConflictResolverDeps,
  lifecycle: BatchLifecycle,
): ConflictResolver {
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
    const item = lifecycle.getCurrentItem()
    if (!item) {
      return false
    }
    const inspection = buildInspectionFromError(error, item.inputPath)
    deps.setPendingConflict({
      itemId: item.id,
      kind: inspection.signatureMatch ? 'final_exists_with_resume' : 'final_exists_only',
      outputPath: inspection.outputPath,
      inspection,
    })
    return true
  }

  return {
    resolveConflict,
    tryStashFromError,
  }
}
