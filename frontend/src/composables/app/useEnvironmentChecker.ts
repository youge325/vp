// 应用层 — 环境探测协调:调用 IPC 并写入 store。

import { useEnvStore } from '@/stores/env'
import { useIssueStore } from '@/stores/issue'
import { envIpc } from '@/lib/ipc/endpoints/env'
import { normalizeError } from '@/lib/errors/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol'

interface EnvironmentCheckOptions {
  forceRefresh?: boolean
  isActive?: () => boolean
}

let latestCheckGeneration = 0

export function useEnvironmentChecker() {
  const envStore = useEnvStore()
  const issueStore = useIssueStore()

  async function checkEnvironment(options: EnvironmentCheckOptions = {}): Promise<void> {
    const { forceRefresh = true, isActive = () => true } = options
    if (!isActive()) {
      return
    }
    const generation = ++latestCheckGeneration
    const canCommit = (): boolean => generation === latestCheckGeneration && isActive()
    envStore.setChecking(true)
    issueStore.clearIssue('environment')
    try {
      const payload = await envIpc.check(forceRefresh)
      if (canCommit()) {
        envStore.setCheckPayload(payload)
      }
    } catch (error) {
      if (canCommit()) {
        issueStore.setIssue('environment', normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
        console.warn('Environment check failed:', error)
      }
    } finally {
      if (canCommit()) {
        envStore.setChecking(false)
      }
    }
  }

  return { checkEnvironment }
}
