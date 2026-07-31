// Pinia store — cross-scope operation issue surface.
// A single store owns user-facing error banners across operation scopes.

import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { OperationIssue, OperationIssueScope } from '@/types/domain/media'
import type { TaskErrorPayload } from '@/types/protocol'

export const useIssueStore = defineStore('issue', () => {
  const operationIssue = ref<OperationIssue | null>(null)

  function setIssue(scope: OperationIssueScope, error: TaskErrorPayload): void {
    operationIssue.value = { scope, error }
  }

  function clearIssue(scope?: OperationIssueScope): void {
    // Only clear when the active issue matches the requested scope
    // (or unconditionally when no scope is given). This lets a
    // success path in scope ``A`` clear its own banner without
    // wiping an unrelated banner currently shown for scope ``B``.
    if (!scope || operationIssue.value?.scope === scope) {
      operationIssue.value = null
    }
  }

  function getIssue(scope: OperationIssueScope): TaskErrorPayload | null {
    return operationIssue.value?.scope === scope ? operationIssue.value.error : null
  }

  return {
    operationIssue,
    setIssue,
    clearIssue,
    getIssue,
  }
})
