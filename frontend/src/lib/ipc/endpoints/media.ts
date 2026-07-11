// IPC endpoints — 媒体导入与探测。

import type { VideoInfo } from '@/types/protocol'
import { safeInvoke } from '../client'

export const mediaIpc = {
  pickInputs(): Promise<string[]> {
    return safeInvoke('pick_inputs')
  },
  inspect(inputPath: string): Promise<VideoInfo> {
    return safeInvoke('inspect_video', { inputPath })
  },
}
