// Pinia store — cross-scope operation issue surface.
//
// Phase 6d — relocated out of ``useMediaStore`` so a single store
// dedicated to user-facing error banners owns the ``operationIssue``
// state across all five scopes (``input / encode / output / task /
// preset``). The previous home in ``useMediaStore`` conflated media
// item state with banner state, which made unit tests for either
// concept import a transitive dependency on the other.

import { ref } from 'vue'
import { defineStore } from 'pinia'

import type { OperationIssue, OperationIssueScope, TaskError } from '@/types/domain/media'

export const useIssueStore = defineStore('issue', () => {
  const operationIssue = ref<OperationIssue | null>(null)

  function setIssue(scope: OperationIssueScope, error: TaskError): void {
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

  function getIssue(scope: OperationIssueScope): TaskError | null {
    return operationIssue.value?.scope === scope ? operationIssue.value.error : null
  }

  return {
    operationIssue,
    setIssue,
    clearIssue,
    getIssue,
  }
})
