// 视图 form-binding — 素材列表编辑器(仅保留联动逻辑与格式化辅助)。
// 删除媒体时同步释放独立的运行时投影,避免遗留孤儿状态。

import { useMediaStore } from '@/stores/media'
import { useMediaRunState } from '@/stores/mediaRunState'
import { getWorkflowSummaryLabel } from '@/services/format/labels'
import type { MediaItem } from '@/types/domain/media'

function formatFps(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.01) {
    return `${Math.round(value)}`
  }
  return value.toFixed(2).replace(/\.?0+$/, '')
}

export function useMediaListEditor() {
  const mediaStore = useMediaStore()
  const runStateStore = useMediaRunState()

  function removeItem(id: string): void {
    mediaStore.removeItem(id)
    runStateStore.dropItem(id)
  }

  return {
    removeItem,
    fpsLabelOf: (item: MediaItem) =>
      item.info ? `${formatFps(item.info.fps)} FPS` : '--',
    workflowLabelOf: (item: MediaItem) => getWorkflowSummaryLabel(item.workflowConfig),
  }
}
