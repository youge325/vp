import { reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  AppEnv,
  EnvironmentCheckPayload,
  EnvironmentCheckResult,
} from '@/types/domain/env'
import type { OperationIssue, OperationIssueScope, TaskError } from '@/types/domain/media'

function createInitialEnv(): AppEnv {
  return {
    lastCheckedAt: null,
    lastProbeAt: null,
    checkSource: null,
    isChecking: false,
    isBootstrapping: false,
    checkResult: null,
    issue: null,
  }
}

export const useEnvStore = defineStore('env', () => {
  const env = reactive<AppEnv>(createInitialEnv())
  const operationIssue = ref<OperationIssue | null>(null)

  function setCheckPayload(payload: EnvironmentCheckPayload, checkedAt: string): void {
    env.checkResult = payload.result
    env.checkSource = payload.source
    env.lastCheckedAt = checkedAt
    env.lastProbeAt = payload.checkedAt ?? checkedAt
  }

  function setCheckResult(result: EnvironmentCheckResult | null): void {
    env.checkResult = result
  }

  function setIssue(issue: TaskError | null): void {
    env.issue = issue
  }

  function setChecking(value: boolean): void {
    env.isChecking = value
  }

  function setBootstrapping(value: boolean): void {
    env.isBootstrapping = value
  }

  function setOperationIssue(scope: OperationIssueScope, error: TaskError): void {
    operationIssue.value = { scope, error }
  }

  function clearOperationIssue(scope?: OperationIssueScope): void {
    if (!scope || operationIssue.value?.scope === scope) {
      operationIssue.value = null
    }
  }

  return {
    env,
    operationIssue,
    setCheckPayload,
    setCheckResult,
    setIssue,
    setChecking,
    setBootstrapping,
    setOperationIssue,
    clearOperationIssue,
  }
})
