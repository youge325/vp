// 视图选择器 — 按 scope 取 OperationIssue,集中替代散布在视图里的字符串比较。

import { computed } from 'vue'
import { useIssueStore } from '@/stores/issue'
import type { OperationIssueScope } from '@/types/domain/media'
import type { TaskErrorPayload } from '@/types/protocol'

export function useOperationIssue(scope: OperationIssueScope) {
  const issueStore = useIssueStore()
  return computed<TaskErrorPayload | null>(() => issueStore.getIssue(scope))
}
