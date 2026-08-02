// Pinia store — cross-scope operation issue surface.
// A single store owns user-facing error banners across operation scopes.

import { reactive } from 'vue'
import { defineStore } from 'pinia'

import type { OperationIssueScope } from '@/types/domain/media'
import type { TaskErrorPayload } from '@/types/protocol'

export const useIssueStore = defineStore('issue', () => {
  const issues = reactive<Partial<Record<OperationIssueScope, TaskErrorPayload>>>({})

  function setIssue(scope: OperationIssueScope, error: TaskErrorPayload): void {
    issues[scope] = error
  }

  function clearIssue(scope?: OperationIssueScope): void {
    if (scope) {
      delete issues[scope]
      return
    }
    for (const activeScope of Object.keys(issues) as OperationIssueScope[]) {
      delete issues[activeScope]
    }
  }

  function getIssue(scope: OperationIssueScope): TaskErrorPayload | null {
    return issues[scope] ?? null
  }

  return {
    setIssue,
    clearIssue,
    getIssue,
  }
})
