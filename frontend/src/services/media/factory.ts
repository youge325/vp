// pure: no Vue / no Pinia / no Tauri
// MediaItem 工厂 — 创建 ID、显示名、初始状态、整体 item。

import type { MediaItem } from '@/types/domain/media'
import type { WorkbenchPreset } from '@/types/protocol'
import { cloneWorkbenchPreset } from '@/services/preset/clone'
import { createIdleTaskState } from '@/services/task/events'

export function createMediaId(path: string): string {
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${Date.now()}-${path.toLowerCase()}-${suffix}`
}

export function basename(path: string): string {
  return path.split(/[/\\]/).pop() ?? path
}

export function createMediaItem(path: string, preset: WorkbenchPreset): MediaItem {
  const snapshot = cloneWorkbenchPreset(preset)
  return {
    id: createMediaId(path),
    inputPath: path,
    displayName: basename(path),
    selected: true,
    inspecting: false,
    info: null,
    issue: null,
    decodeConfig: snapshot.decodeConfig,
    workflowConfig: snapshot.workflowConfig,
    encodeConfig: snapshot.encodeConfig,
    outputConfig: snapshot.outputConfig,
    taskState: createIdleTaskState(),
    lastOutputPath: '',
  }
}
