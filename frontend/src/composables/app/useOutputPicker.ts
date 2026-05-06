// 应用层 — 输出目录选择协调。

import { usePresetStore } from '@/stores/preset'
import { presetIpc } from '@/lib/ipc/endpoints/preset'
import { normalizeTaskError } from '@/services/task/error-normalizer'
import type { TaskError } from '@/types/domain/media'

export function useOutputPicker() {
  const presetStore = usePresetStore()

  async function pickOutputDirectory(): Promise<{ outputDir: string | null; error: TaskError | null }> {
    try {
      const outputDir = await presetIpc.pickOutputDirectory()
      if (outputDir) {
        presetStore.patchOutput((config) => {
          config.outputDir = outputDir
        })
      }
      return { outputDir, error: null }
    } catch (error) {
      return { outputDir: null, error: normalizeTaskError(error, 'pick_output_dir_failed') }
    }
  }

  return { pickOutputDirectory }
}
