// 视图选择器 — 按 scope 取 OperationIssue,集中替代散布在视图里的字符串比较。

import { computed } from 'vue'
import { useMediaStore } from '@/stores/media'
import type { OperationIssueScope, TaskError } from '@/types/domain/media'

export function useOperationIssue(scope: OperationIssueScope) {
  const mediaStore = useMediaStore()
  return computed<TaskError | null>(() =>
    mediaStore.operationIssue?.scope === scope ? mediaStore.operationIssue.error : null,
  )
}
