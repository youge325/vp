// 应用层 — 输出目录选择协调。

import { usePresetStore } from '@/stores/preset'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
import { normalizeError } from '@/services/error/normalize'
import type { TaskError } from '@/types/domain/media'
import { TASK_ERROR_CODES } from '@/types/protocol/errors'
import type { OutputConfig } from '@/types/protocol'

export function useOutputPicker() {
  const presetStore = usePresetStore()

  async function pickOutputDirectory(): Promise<{ outputDir: string | null; error: TaskError | null }> {
    try {
      const outputDir = await presetIpc.pickOutputDirectory()
      if (outputDir) {
        presetStore.patchOutput((config: OutputConfig) => {
          config.outputDir = outputDir
        })
      }
      return { outputDir, error: null }
    } catch (error) {
      return { outputDir: null, error: normalizeError(error, TASK_ERROR_CODES.IoError) }
    }
  }

  return { pickOutputDirectory }
}
