// pure: no Vue / no Pinia / no Tauri
// MediaItem 工厂 — 创建 ID、显示名、初始状态、整体 item。

import type { MediaItem } from '@/types/domain/media'
import type { WorkbenchPreset } from '@/types/protocol'
import { cloneWorkbenchPreset } from '@/services/preset/clone'

export function createMediaId(path: string): string {
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${Date.now()}-${path.toLowerCase()}-${suffix}`
}

export function basename(path: string): string {
  return path.split(/[/\\]/).pop() ?? path
}

// Phase 13.1 — taskState / issue / lastOutputPath 从 ``MediaItem`` 移走
// 到 [[useMediaRunState]],``createMediaItem`` 不再初始化运行时投影:
// run state 在第一次 setItemTaskState / setItemIssue / setItemLastOutputPath
// 被调用时由 store 内部 lazy 创建。
export function createMediaItem(path: string, preset: WorkbenchPreset): MediaItem {
  const snapshot = cloneWorkbenchPreset(preset)
  return {
    id: createMediaId(path),
    inputPath: path,
    displayName: basename(path),
    selected: true,
    inspecting: false,
    info: null,
    decodeConfig: snapshot.decodeConfig,
    workflowConfig: snapshot.workflowConfig,
    encodeConfig: snapshot.encodeConfig,
    outputConfig: snapshot.outputConfig,
  }
}
