// pure: no Vue / no Pinia / no Tauri
// MediaItem 工厂 — 创建 ID、显示名、初始状态、整体 item。

import type { MediaItem } from '@/types/domain/media'
import type { WorkbenchPreset } from '@/types/protocol'
import { clonePresetData } from '@/services/preset/clone'

function createMediaId(path: string): string {
  const suffix = Math.random().toString(36).slice(2, 8)
  return `${Date.now()}-${path.toLowerCase()}-${suffix}`
}

function basename(path: string): string {
  return path.split(/[/\\]/).pop() ?? path
}

// 运行时投影由 ``useMediaRunState`` 按需创建;本工厂只创建媒体实体。
export function createMediaItem(path: string, preset: WorkbenchPreset): MediaItem {
  const snapshot = clonePresetData(preset)
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
