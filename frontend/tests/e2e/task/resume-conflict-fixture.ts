import type { ResumeConflictDescriptor } from '@/types/domain/batch'
import { withPiniaState } from '../utils/wdio-tauri'

export async function injectResumeConflict(
  descriptor: ResumeConflictDescriptor,
): Promise<boolean> {
  return await withPiniaState((state, _win, conflict) => {
    const task = state.task as { pendingConflict?: ResumeConflictDescriptor | null } | undefined
    if (!task) {
      return false
    }
    task.pendingConflict = conflict
    return true
  }, descriptor)
}

export async function clearResumeConflict(): Promise<void> {
  await withPiniaState((state) => {
    const task = state.task as { pendingConflict?: ResumeConflictDescriptor | null } | undefined
    if (task) {
      task.pendingConflict = null
    }
  })
}
