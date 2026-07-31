import { reactive } from 'vue'
import { defineStore } from 'pinia'
import type {
  EnvironmentCheckResult,
  EnvironmentCheckPayload,
  EnvironmentCheckSource,
  TaskErrorPayload,
} from '@/types/protocol'

interface AppEnv {
  lastProbeAt: string | null
  checkSource: EnvironmentCheckSource | null
  isChecking: boolean
  isBootstrapping: boolean
  checkResult: EnvironmentCheckResult | null
  issue: TaskErrorPayload | null
}

function createInitialEnv(): AppEnv {
  return {
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

  function setCheckPayload(payload: EnvironmentCheckPayload): void {
    env.checkResult = payload.result
    env.checkSource = payload.source
    env.lastProbeAt = payload.checkedAt
  }

  function setIssue(issue: TaskErrorPayload | null): void {
    env.issue = issue
  }

  function setChecking(value: boolean): void {
    env.isChecking = value
  }

  function setBootstrapping(value: boolean): void {
    env.isBootstrapping = value
  }

  return {
    env,
    setCheckPayload,
    setIssue,
    setChecking,
    setBootstrapping,
  }
})
