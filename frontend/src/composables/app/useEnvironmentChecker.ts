// 应用层 — 环境探测协调:调用 IPC 并写入 store。

import { useEnvStore } from '@/stores/env'
import { envIpc } from '@/lib/ipc/endpoints/env'
import { normalizeError } from '@/lib/errors/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol'
import type { EnvironmentCheckPayload } from '@/types/protocol'

export function requestEnvironmentCheck(forceRefresh = true): Promise<EnvironmentCheckPayload> {
  return envIpc.check(forceRefresh)
}

export function useEnvironmentChecker() {
  const envStore = useEnvStore()

  async function recheckEnvironment(forceRefresh = true): Promise<void> {
    envStore.setChecking(true)
    envStore.setIssue(null)
    try {
      envStore.setCheckPayload(await requestEnvironmentCheck(forceRefresh))
    } catch (error) {
      // Structured shell errors retain their code; unknown failures
      // use the canonical process error fallback.
      envStore.setIssue(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    } finally {
      envStore.setChecking(false)
    }
  }

  return { recheckEnvironment }
}
