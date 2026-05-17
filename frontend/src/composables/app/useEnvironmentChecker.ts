// 应用层 — 环境探测协调:调用 IPC、归一化结果、写入 store。

import { useEnvStore } from '@/stores/env'
import { envIpc } from '@/lib/ipc/endpoints/env'
import { normalizeCheckPayload } from '@/services/env/normalize'
import { normalizeError } from '@/services/error/normalize'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'

export function useEnvironmentChecker() {
  const envStore = useEnvStore()

  async function recheckEnvironment(forceRefresh = true): Promise<void> {
    envStore.setChecking(true)
    envStore.setIssue(null)
    try {
      const payload = normalizeCheckPayload(await envIpc.check(forceRefresh))
      envStore.setCheckPayload(payload, new Date().toISOString())
    } catch (error) {
      // Phase 6c — fallback narrowed from the legacy magic string
      // ``'check_failed'`` to the enum value. Real failure codes
      // come from the Rust ShellError envelope; this path only
      // triggers when the error has no ``code`` field at all.
      envStore.setIssue(normalizeError(error, TASK_ERROR_CODES.ProcessFailed))
    } finally {
      envStore.setChecking(false)
    }
  }

  return { recheckEnvironment }
}
