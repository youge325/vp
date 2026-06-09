// IPC endpoints — 环境探测。

import type { EnvironmentCheckPayload } from '@/types/domain/env'
import { safeInvoke } from '../client'

export const envIpc = {
  check(forceRefresh = false): Promise<EnvironmentCheckPayload> {
    return safeInvoke('check_environment', { forceRefresh })
  },
}
