// 视图选择器 — 按 scope 取 OperationIssue,集中替代散布在视图里的字符串比较。

import { computed } from 'vue'
import { useEnvStore } from '@/stores/env'
import type { OperationIssueScope, TaskError } from '@/types/domain/media'

export function useEnvIssue(scope: OperationIssueScope) {
  const envStore = useEnvStore()
  return computed<TaskError | null>(() =>
    envStore.operationIssue?.scope === scope ? envStore.operationIssue.error : null,
  )
}
