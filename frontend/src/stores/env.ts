import { reactive } from 'vue'
import { defineStore } from 'pinia'
import type {
  AppEnv,
  EnvironmentCheckPayload,
} from '@/types/domain/env'
import type { TaskError } from '@/types/domain/media'

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

  function setCheckPayload(payload: EnvironmentCheckPayload, checkedAt: string): void {
    env.checkResult = payload.result
    env.checkSource = payload.source
    env.lastCheckedAt = checkedAt
    env.lastProbeAt = payload.checkedAt ?? checkedAt
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

  return {
    env,
    setCheckPayload,
    setIssue,
    setChecking,
    setBootstrapping,
  }
})
