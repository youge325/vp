// IPC endpoints — 预设持久化与输出目录选择。

import type { WorkbenchPreset } from '@/types/protocol'
import { isTauriRuntime, safeInvoke } from '../client'

export const presetIpc = {
  load(): Promise<WorkbenchPreset | null> {
    if (!isTauriRuntime()) {
      return Promise.resolve(null)
    }
    return safeInvoke<WorkbenchPreset | null>('load_workbench_preset')
  },
  save(preset: WorkbenchPreset): Promise<void> {
    if (!isTauriRuntime()) {
      return Promise.resolve()
    }
    return safeInvoke<void>('save_workbench_preset', { preset })
  },
  pickOutputDirectory(): Promise<string | null> {
    return safeInvoke<string | null>('pick_output_directory')
  },
}
