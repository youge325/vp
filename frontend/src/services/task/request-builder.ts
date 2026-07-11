// pure: no Vue / no Pinia / no Tauri
// 任务请求构建 — 把 MediaItem 投影成 IPC TaskRequest。

import type { ResumeMode, TaskRequest } from '@/types/protocol'
import type { MediaItem } from '@/types/domain/media'

export function buildTaskRequest(item: MediaItem, resumeMode?: ResumeMode): TaskRequest {
  return {
    inputPath: item.inputPath,
    decodeConfig: item.decodeConfig,
    workflowConfig: item.workflowConfig,
    encodeConfig: item.encodeConfig,
    outputConfig: item.outputConfig,
    ...(resumeMode ? { resumeMode } : {}),
  }
}
