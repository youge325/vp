// IPC endpoints — 媒体导入与探测。

import type { VideoInfoResult } from '@/types/domain/media'
import { safeInvoke } from '../client'

export const mediaIpc = {
  pickInputs(): Promise<string[]> {
    return safeInvoke('pick_inputs')
  },
  inspect(inputPath: string): Promise<VideoInfoResult> {
    return safeInvoke('inspect_video', { inputPath })
  },
}
