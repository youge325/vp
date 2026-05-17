// 视图选择器 — 按 scope 取 OperationIssue,集中替代散布在视图里的字符串比较。
//
// Phase 6d — 数据源从 ``useMediaStore`` 迁移到 ``useIssueStore``。
// Selector 接口保持不变,callsite 不需要改动。

import { computed } from 'vue'
import { useIssueStore } from '@/stores/issue'
import type { OperationIssueScope, TaskError } from '@/types/domain/media'

export function useOperationIssue(scope: OperationIssueScope) {
  const issueStore = useIssueStore()
  return computed<TaskError | null>(() => issueStore.getIssue(scope))
}
