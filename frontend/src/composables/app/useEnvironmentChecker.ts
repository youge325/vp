// 应用层 — 环境探测协调:调用 IPC、归一化结果、写入 store。

import { useEnvStore } from '@/stores/env'
import { envIpc } from '@/lib/ipc/endpoints/env'
import { normalizeCheckPayload } from '@/services/env/normalize'
import { normalizeTaskError } from '@/services/task/error-normalizer'

export function useEnvironmentChecker() {
  const envStore = useEnvStore()

  async function recheckEnvironment(forceRefresh = true): Promise<void> {
    envStore.setChecking(true)
    envStore.setIssue(null)
    try {
      const payload = normalizeCheckPayload(await envIpc.check(forceRefresh))
      envStore.setCheckPayload(payload, new Date().toISOString())
    } catch (error) {
      envStore.setIssue(normalizeTaskError(error, 'check_failed'))
    } finally {
      envStore.setChecking(false)
    }
  }

  return { recheckEnvironment }
}
